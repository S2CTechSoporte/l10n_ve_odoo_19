from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRateEntries(DualCurrencyTestCommon):
    """Manual journal entries converted at the manual rate captured in the entry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls._set_rate(cls.eur, cls.company, cls.rate_date_invoice, 55.0)
        cls.expense = cls.company_data["default_account_expense"]
        cls.revenue = cls.company_data["default_account_revenue"]
        cls.receivable = cls.company_data["default_account_receivable"]

    def _usd_entry(self, amount=100.0, **values):
        return self._create_entry(
            [(self.expense, self.usd, amount), (self.revenue, self.usd, -amount)],
            **values,
        )

    def _items(self, entry):
        return entry.line_ids.sorted("id")

    def _receivable_item(self, entry):
        return entry.line_ids.filtered(lambda line: line.account_id == self.receivable)

    def _settlement_entry(self, amount, **values):
        """Entry that credits the receivable of the customer, like a withholding does."""
        return self._create_entry(
            [
                (
                    self.receivable,
                    self.ves,
                    -amount,
                    {"partner_id": self.partner_customer.id},
                ),
                (self.expense, self.ves, amount),
            ],
            **values,
        )

    # ------------------------------------------------------------------ amounts

    def test_manual_rate_drives_the_balance_and_the_reference_amounts_of_foreign_items(self):
        entry = self._usd_entry(manual_rate=60.0)
        debit_item, credit_item = self._items(entry)
        self.assertTrue(entry.manual_rate_available)
        self.assertTrue(entry.manual_rate_active)
        self.assertAlmostEqual(debit_item.amount_currency, 100.0)
        self.assertAlmostEqual(debit_item.currency_rate, 1 / 60.0)
        self.assertAlmostEqual(debit_item.balance, 6000.0)
        self.assertAlmostEqual(debit_item.debit, 6000.0)
        self.assertAlmostEqual(credit_item.balance, -6000.0)
        self.assertAlmostEqual(credit_item.credit, 6000.0)
        self.assertAlmostEqual(debit_item.conversion_rate, 60.0)
        self.assertAlmostEqual(debit_item.debit_secondary_currency, 100.0)
        self.assertAlmostEqual(credit_item.credit_secondary_currency, 100.0)
        self.assertAlmostEqual(credit_item.balance_secondary_currency, -100.0)
        self.assertAlmostEqual(entry.conversion_rate, 60.0)
        self.assertAlmostEqual(entry.conversion_rate_display, 60.0)
        self.assertEqual(entry.conversion_rate_display_currency_id, self.ves)

    def test_entry_without_manual_rate_keeps_the_system_rate(self):
        entry = self._usd_entry()
        debit_item, credit_item = self._items(entry)
        self.assertTrue(entry.manual_rate_available)
        self.assertFalse(entry.manual_rate_active)
        self.assertAlmostEqual(debit_item.currency_rate, 1 / 50.0)
        self.assertAlmostEqual(debit_item.balance, 5000.0)
        self.assertAlmostEqual(credit_item.balance, -5000.0)
        self.assertAlmostEqual(debit_item.debit_secondary_currency, 100.0)
        self.assertAlmostEqual(entry.conversion_rate, 50.0)

    def test_manual_rate_drives_the_reference_amounts_of_company_currency_items(self):
        for manual_rate, rate, reference in ((60.0, 60.0, 100.0), (None, 50.0, 120.0)):
            with self.subTest(manual_rate=manual_rate):
                entry = self._create_entry(
                    [(self.expense, self.ves, 6000.0), (self.revenue, self.ves, -6000.0)],
                    manual_rate=manual_rate,
                )
                debit_item, credit_item = self._items(entry)
                self.assertAlmostEqual(debit_item.balance, 6000.0)
                self.assertAlmostEqual(debit_item.conversion_rate, rate)
                self.assertAlmostEqual(debit_item.debit_secondary_currency, reference)
                self.assertAlmostEqual(credit_item.balance_secondary_currency, -reference)

    def test_entry_mixing_foreign_and_company_currency_items_balances_at_the_manual_rate(self):
        items = [(self.expense, self.usd, 100.0), (self.revenue, self.ves, -6000.0)]
        entry = self._create_entry(items, manual_rate=60.0)
        foreign_item, company_item = self._items(entry)
        self.assertAlmostEqual(foreign_item.balance, 6000.0)
        self.assertAlmostEqual(foreign_item.balance_secondary_currency, 100.0)
        self.assertAlmostEqual(company_item.balance_secondary_currency, -100.0)
        # At the system rate the same entry is not balanced: 100 USD are 5.000 VES.
        with self._assert_error(UserError, "not balanced"):
            self._create_entry(items)

    # ------------------------------------------------------------ draft changes

    def test_changing_the_rate_of_a_draft_entry_converts_the_foreign_items(self):
        entry = self._usd_entry(post=False)
        debit_item, credit_item = self._items(entry)
        self.assertAlmostEqual(debit_item.balance, 5000.0)

        entry.write({"manual_rate": True, "manual_conversion_rate": 60.0})
        self.assertAlmostEqual(debit_item.balance, 6000.0)
        self.assertAlmostEqual(debit_item.debit, 6000.0)
        self.assertAlmostEqual(credit_item.balance, -6000.0)
        self.assertAlmostEqual(debit_item.debit_secondary_currency, 100.0)

        entry.manual_conversion_rate = 70.0
        self.assertAlmostEqual(debit_item.balance, 7000.0)
        self.assertAlmostEqual(credit_item.credit, 7000.0)
        self.assertAlmostEqual(debit_item.debit_secondary_currency, 100.0)

        entry.manual_rate = False
        self.assertAlmostEqual(debit_item.balance, 5000.0)
        self.assertAlmostEqual(credit_item.balance, -5000.0)
        self.assertAlmostEqual(debit_item.conversion_rate, 50.0)

    def test_changing_the_rate_of_a_draft_entry_keeps_the_company_currency_items(self):
        entry = self._create_entry(
            [(self.expense, self.ves, 6000.0), (self.revenue, self.ves, -6000.0)],
            post=False,
        )
        entry.write({"manual_rate": True, "manual_conversion_rate": 60.0})
        debit_item, credit_item = self._items(entry)
        self.assertAlmostEqual(debit_item.balance, 6000.0)
        self.assertAlmostEqual(credit_item.balance, -6000.0)
        self.assertAlmostEqual(debit_item.debit_secondary_currency, 100.0)

    def test_changing_the_rate_of_a_draft_entry_must_leave_it_balanced(self):
        entry = self._create_entry(
            [(self.expense, self.usd, 100.0), (self.revenue, self.ves, -5000.0)],
            post=False,
        )
        foreign_item, company_item = self._items(entry)
        with self._assert_error(UserError, "not balanced"):
            entry.write({"manual_rate": True, "manual_conversion_rate": 60.0})
        entry.invalidate_recordset()
        foreign_item.invalidate_recordset()
        self.assertFalse(entry.manual_rate)
        self.assertAlmostEqual(foreign_item.balance, 5000.0)

        # The counterpart is changed in the same write: the entry stays balanced.
        entry.write(
            {
                "manual_rate": True,
                "manual_conversion_rate": 60.0,
                "line_ids": [Command.update(company_item.id, {"balance": -6000.0})],
            }
        )
        self.assertAlmostEqual(foreign_item.balance, 6000.0)
        self.assertAlmostEqual(company_item.balance, -6000.0)
        entry.action_post()
        self.assertEqual(entry.state, "posted")

    def test_manual_rate_of_a_posted_entry_cannot_be_modified(self):
        entry = self._usd_entry(manual_rate=60.0)
        with self._assert_error(UserError, "cannot modify the manual rate"):
            entry.manual_conversion_rate = 70.0
        with self._assert_error(UserError, "cannot modify the manual rate"):
            entry.manual_rate = False
        entry.button_draft()
        entry.manual_conversion_rate = 70.0
        self.assertAlmostEqual(self._items(entry)[0].balance, 7000.0)
        entry.action_post()
        self.assertAlmostEqual(self._items(entry)[0].debit, 7000.0)

    def test_editing_a_foreign_amount_uses_the_manual_rate(self):
        entry = self._usd_entry(manual_rate=60.0, post=False)
        debit_item, credit_item = self._items(entry)
        entry.write(
            {
                "line_ids": [
                    Command.update(debit_item.id, {"amount_currency": 200.0}),
                    Command.update(credit_item.id, {"amount_currency": -200.0}),
                ]
            }
        )
        self.assertAlmostEqual(debit_item.balance, 12000.0)
        self.assertAlmostEqual(credit_item.balance, -12000.0)
        self.assertAlmostEqual(debit_item.debit_secondary_currency, 200.0)

    # ------------------------------------------------------------------ currencies

    def test_manual_rate_is_not_available_in_a_journal_of_a_third_currency(self):
        self.misc_journal.currency_id = self.eur
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": self.rate_date_invoice,
            }
        )
        self.assertEqual(entry.currency_id, self.eur)
        self.assertFalse(entry.manual_rate_available)
        with self._assert_error(ValidationError, "manual rate is only available"):
            entry.write({"manual_rate": True, "manual_conversion_rate": 60.0})

    def test_entry_with_a_third_currency_item_rejects_the_manual_rate(self):
        eur_items = [(self.expense, self.eur, 100.0), (self.revenue, self.eur, -100.0)]
        with self._assert_error(ValidationError, "can only have journal items"):
            self._create_entry(eur_items, manual_rate=60.0, post=False)

        entry = self._create_entry(eur_items, post=False)
        self.assertTrue(entry.line_ids)
        with self._assert_error(ValidationError, "can only have journal items"):
            entry.write({"manual_rate": True, "manual_conversion_rate": 60.0})

    def test_manual_rate_entry_rejects_the_items_of_a_third_currency(self):
        entry = self._usd_entry(manual_rate=60.0, post=False)
        with self._assert_error(ValidationError, "can only have journal items"):
            entry.write(
                {
                    "line_ids": [
                        Command.create(
                            {
                                "name": "EUR item",
                                "account_id": self.expense.id,
                                "currency_id": self.eur.id,
                                "amount_currency": 100.0,
                                "balance": 0.0,
                            }
                        )
                    ]
                }
            )
        with self._assert_error(ValidationError, "can only have journal items"):
            self._items(entry)[0].currency_id = self.eur

    # ------------------------------------------------------------------- the form

    def _entry_form(self):
        form = Form(
            self.env["account.move"].with_context(
                default_move_type="entry", default_journal_id=self.misc_journal.id
            )
        )
        form.date = self.rate_date_invoice
        return form

    def _add_usd_item(self, form, account, amount):
        with form.line_ids.new() as item:
            item.name = account.name
            item.account_id = account
            item.currency_id = self.usd
            item.amount_currency = amount

    def test_form_converts_the_items_entered_after_the_manual_rate(self):
        form = self._entry_form()
        self.assertFalse(form.manual_rate)
        form.manual_rate = True
        self.assertAlmostEqual(form.manual_conversion_rate, 50.0)
        form.manual_conversion_rate = 60.0
        self._add_usd_item(form, self.expense, 100.0)
        self._add_usd_item(form, self.revenue, -100.0)
        entry = form.save()
        self.assertTrue(entry.manual_rate_active)
        self.assertEqual(
            [item.balance for item in self._items(entry)], [6000.0, -6000.0]
        )
        self.assertAlmostEqual(self._items(entry)[0].debit_secondary_currency, 100.0)

    def test_form_converts_the_items_entered_before_the_manual_rate(self):
        form = self._entry_form()
        self._add_usd_item(form, self.expense, 100.0)
        self._add_usd_item(form, self.revenue, -100.0)
        form.manual_rate = True
        form.manual_conversion_rate = 60.0
        entry = form.save()
        self.assertTrue(entry.manual_rate_active)
        self.assertEqual(
            [item.balance for item in self._items(entry)], [6000.0, -6000.0]
        )

    def test_form_of_a_payment_entry_does_not_offer_the_manual_rate(self):
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, manual_rate=60.0
        )
        payment.action_draft()
        form = Form(payment.move_id)
        with self.assertRaises(AssertionError):
            form.manual_rate = False

    # --------------------------------------------------------------- reversals

    def test_reversal_of_a_manual_rate_entry_keeps_the_rate(self):
        entry = self._usd_entry(manual_rate=60.0)
        reversal = self._create_credit_note(entry, self.rate_date_third)
        self.assertEqual(reversal.move_type, "entry")
        self.assertEqual(reversal.reversed_entry_id, entry)
        self.assertTrue(reversal.manual_rate_active)
        self.assertAlmostEqual(reversal.manual_conversion_rate, 60.0)
        for item, original in zip(self._items(reversal), self._items(entry)):
            self.assertAlmostEqual(item.balance, -original.balance)
            self.assertAlmostEqual(
                item.balance_secondary_currency, -original.balance_secondary_currency
            )

    def test_reversal_of_a_system_rate_entry_has_no_manual_rate(self):
        entry = self._usd_entry()
        reversal = self._create_credit_note(entry, self.rate_date_third)
        self.assertFalse(reversal.manual_rate)
        self.assertEqual(reversal.manual_conversion_rate, 0.0)

    def test_reversal_of_a_payment_entry_keeps_its_manual_rate(self):
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, manual_rate=60.0
        )
        reversal = self._create_credit_note(payment.move_id, self.rate_date_third)
        self.assertTrue(reversal.manual_rate_active)
        self.assertAlmostEqual(reversal.manual_conversion_rate, 60.0)
        for item, original in zip(self._items(reversal), self._items(payment.move_id)):
            self.assertAlmostEqual(
                item.balance_secondary_currency, -original.balance_secondary_currency
            )

    # ---------------------------------------------------------- reconciliation

    def test_entry_settles_an_invoice_at_its_own_manual_rate(self):
        for entry_rate, residual in ((60.0, 50.0), (None, 40.0)):
            with self.subTest(entry_rate=entry_rate):
                invoice = self._create_invoice(
                    self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
                )
                entry = self._settlement_entry(3000.0, manual_rate=entry_rate)
                (
                    self._get_payment_term_line(invoice) + self._receivable_item(entry)
                ).reconcile()
                # 3000 / 60 = 50 USD; at the system rate it would be 3000 / 50 = 60 USD.
                self.assertEqual(invoice.payment_state, "partial")
                self.assertAlmostEqual(invoice.amount_residual, residual)
                self.assertAlmostEqual(invoice.amount_residual_secondary_currency, residual)

    def test_manual_rate_of_an_invoice_wins_over_the_rate_of_a_later_entry(self):
        invoice = self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        entry = self._settlement_entry(
            3000.0, entry_date=self.rate_date_third, manual_rate=62.0
        )
        (self._get_payment_term_line(invoice) + self._receivable_item(entry)).reconcile()
        partial = self._get_payment_term_line(invoice).matched_credit_ids
        self.assertEqual(len(partial), 1)
        # The invoice settles the partial: 3000 / 60, not 3000 / 62 of the later entry.
        self.assertAlmostEqual(partial.amount_secondary_currency, 50.0)

    def test_manual_rate_of_a_payment_wins_over_the_rate_of_an_entry(self):
        # The entry debits the receivable of the customer and the payment settles it.
        entry = self._create_entry(
            [
                (
                    self.receivable,
                    self.ves,
                    3000.0,
                    {"partner_id": self.partner_customer.id},
                ),
                (self.revenue, self.ves, -3000.0),
            ],
            manual_rate=62.0,
        )
        payment = self._create_direct_payment(
            self.ves, 3000.0, self.rate_date_third, "inbound", manual_rate=60.0
        )
        (
            self._receivable_item(entry)
            + payment.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
            )
        ).reconcile()
        partial = self._receivable_item(entry).matched_credit_ids
        self.assertEqual(len(partial), 1)
        # The payment settles the partial: 3000 / 60, not 3000 / 62 of the entry.
        self.assertAlmostEqual(partial.amount_secondary_currency, 50.0)
