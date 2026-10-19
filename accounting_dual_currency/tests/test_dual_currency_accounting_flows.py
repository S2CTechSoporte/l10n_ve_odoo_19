from odoo import Command
from odoo.tests import Form, tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestDualCurrencyAccountingFlows(DualCurrencyTestCommon):
    def _create_credit_note(self, invoice, reversal_date):
        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create(
            {
                "move_ids": [(6, 0, invoice.ids)],
                "company_id": self.company.id,
                "journal_id": invoice.journal_id.id,
                "date": reversal_date,
                "reason": "Dual currency reversal test",
            }
        )
        wizard.refund_moves()
        credit_note = wizard.new_move_ids[:1]
        if credit_note.state == "draft":
            credit_note.action_post()
        return credit_note

    def test_ves_credit_note_reuses_original_invoice_rate(self):
        invoice = self._create_invoice(
            self.ves,
            5000.0,
            self.rate_date_invoice,
        )
        credit_note = self._create_credit_note(invoice, self.rate_date_third)
        credit_line = credit_note.invoice_line_ids[:1]
        term_line = self._get_payment_term_line(credit_note)

        self.assertAlmostEqual(invoice.conversion_rate, 50.0, places=2)
        self.assertAlmostEqual(credit_note.conversion_rate, 50.0, places=2)
        self.assertAlmostEqual(credit_note.conversion_rate_display, 50.0, places=2)
        self.assertEqual(credit_note.conversion_rate_display_currency_id, self.ves)
        self.assertAlmostEqual(credit_line.conversion_rate, 50.0, places=2)
        self.assertAlmostEqual(abs(credit_line.balance_secondary_currency), 100.0, places=2)
        self.assertAlmostEqual(abs(term_line.balance_secondary_currency), 100.0, places=2)
        self.assertAlmostEqual(credit_note.amount_total_secondary_currency, 100.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual_secondary_currency, 0.0, places=2)

    def test_usd_credit_note_reuses_original_invoice_rate(self):
        invoice = self._create_invoice(
            self.usd,
            100.0,
            self.rate_date_invoice,
        )
        credit_note = self._create_credit_note(invoice, self.rate_date_third)
        credit_line = credit_note.invoice_line_ids[:1]

        # Odoo copies the rate of the invoice in the reversal wizard, so the credit
        # note cancels it in company currency and its reference amounts follow it.
        self.assertAlmostEqual(credit_note.invoice_currency_rate, 1 / 50.0, places=9)
        self.assertAlmostEqual(abs(credit_line.balance), 5000.0, places=2)
        self.assertAlmostEqual(credit_line.conversion_rate, 50.0, places=2)
        self.assertAlmostEqual(abs(credit_line.balance_secondary_currency), 100.0, places=2)
        self.assertAlmostEqual(
            credit_note.amount_total_local_currency,
            5000.0,
            places=2,
        )
        self.assertAlmostEqual(credit_note.amount_total_secondary_currency, 100.0, places=2)

    def test_usd_credit_note_without_the_original_rate_uses_its_own_date(self):
        invoice = self._create_invoice(
            self.usd,
            100.0,
            self.rate_date_invoice,
        )
        credit_note = invoice._reverse_moves(
            [{"date": self.rate_date_third, "invoice_date": self.rate_date_third}]
        )
        credit_note.action_post()
        credit_line = credit_note.invoice_line_ids[:1]

        # A reversal that does not copy the rate converts at the date of the note.
        self.assertAlmostEqual(credit_note.invoice_currency_rate, 1 / 54.0, places=9)
        self.assertAlmostEqual(abs(credit_line.balance), 5400.0, places=2)
        self.assertAlmostEqual(credit_line.conversion_rate, 54.0, places=2)
        self.assertAlmostEqual(abs(credit_line.balance_secondary_currency), 100.0, places=2)
        self.assertAlmostEqual(
            credit_note.amount_total_local_currency,
            5400.0,
            places=2,
        )
        self.assertAlmostEqual(credit_note.amount_total_secondary_currency, 100.0, places=2)

    def test_manual_usd_entry_keeps_ves_and_reference_balances(self):
        move_form = Form(
            self.env["account.move"].with_context(
                default_move_type="entry",
                default_journal_id=self.misc_journal.id,
            )
        )
        move_form.date = self.rate_date_invoice
        move_form.journal_id = self.misc_journal
        with move_form.line_ids.new() as debit_line:
            debit_line.name = "USD debit"
            debit_line.account_id = self.company_data["default_account_expense"]
            debit_line.currency_id = self.usd
            debit_line.amount_currency = 200.0
        with move_form.line_ids.new() as credit_line:
            credit_line.name = "USD credit"
            credit_line.account_id = self.company_data["default_account_revenue"]
            credit_line.currency_id = self.usd
            credit_line.amount_currency = -200.0

        move = move_form.save()
        self.assertAlmostEqual(move.conversion_rate, 50.0, places=2)
        self.assertAlmostEqual(move.conversion_rate_display, 50.0, places=2)
        self.assertEqual(move.conversion_rate_display_currency_id, self.ves)
        foreign_lines = move.line_ids.filtered(lambda line: line.currency_id == self.usd)
        self.assertEqual(len(foreign_lines), 2)
        self.assertEqual(
            sorted(self.ves.round(abs(line.balance)) for line in foreign_lines),
            [10000.0, 10000.0],
        )
        self.assertEqual(
            sorted(self.usd.round(abs(line.balance_secondary_currency)) for line in foreign_lines),
            [200.0, 200.0],
        )

    def test_missing_reference_currency_falls_back_to_ves(self):
        self.company.secondary_currency_id = False
        invoice = self._create_invoice(
            self.ves,
            5000.0,
            self.rate_date_invoice,
        )
        self.assertFalse(invoice.secondary_currency_id)
        self.assertAlmostEqual(invoice.conversion_rate, 1.0, places=2)
        self.assertAlmostEqual(invoice.amount_total_secondary_currency, 5000.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual_secondary_currency, 5000.0, places=2)
        self.assertAlmostEqual(
            abs(self._get_payment_term_line(invoice).balance_secondary_currency),
            5000.0,
            places=2,
        )

    def test_reference_currency_default_for_other_company_currency(self):
        eur = self.env.ref("base.EUR")
        company = self.env["res.company"].create(
            {"name": "Dual Currency EUR Company", "currency_id": eur.id}
        )
        companies = self.env["res.company"].with_company(company)

        self.assertEqual(companies._get_secondary_currency_id(), self.usd)

        company.currency_id = self.usd
        self.assertFalse(companies._get_secondary_currency_id())

    def test_eur_company_invoice_payment_and_aged_currency_options(self):
        eur = self.env.ref("base.EUR")
        eur.active = True
        self.company.write({"currency_id": eur.id, "secondary_currency_id": self.usd.id})
        self._set_rate(self.usd, self.company, self.rate_date_invoice, 0.8)

        invoice = self._create_invoice(eur, 80.0, self.rate_date_invoice)
        self.assertEqual(invoice.company_currency_id, eur)
        self.assertAlmostEqual(invoice.amount_total_local_currency, 80.0, places=2)
        self.assertAlmostEqual(invoice.amount_total_secondary_currency, 100.0, places=2)

        _, options = self._get_report_options(
            "account_reports.aged_receivable_report", self.rate_date_invoice
        )
        self.assertEqual(options["dual_currency_id"], eur.id)
        self.assertEqual(
            {currency["currency_id"] for currency in options["dual_currencies"]},
            {eur.id, self.usd.id},
        )

        payment = self._create_payment(invoice, self.usd, 100.0, self.rate_date_invoice)
        self.assertAlmostEqual(payment.amount_local, 80.0, places=2)
        self.assertAlmostEqual(payment.amount_ref, 100.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual_secondary_currency, 0.0, places=2)

    def test_usd_company_eur_reference_invoice_and_payment(self):
        eur = self.env.ref("base.EUR")
        eur.active = True
        self.company.write({"currency_id": self.usd.id, "secondary_currency_id": eur.id})
        self._set_rate(self.usd, self.company, self.rate_date_invoice, 1.0)
        self._set_rate(eur, self.company, self.rate_date_invoice, 1.25)

        invoice = self._create_invoice(self.usd, 100.0, self.rate_date_invoice)
        self.assertEqual(invoice.secondary_currency_id, eur)
        self.assertAlmostEqual(invoice.amount_total_local_currency, 100.0, places=2)
        self.assertAlmostEqual(invoice.amount_total_secondary_currency, 80.0, places=2)

        _, options = self._get_report_options(
            "account_reports.aged_receivable_report", self.rate_date_invoice
        )
        self.assertEqual(options["dual_currency_id"], self.usd.id)
        self.assertEqual(
            {currency["currency_id"] for currency in options["dual_currencies"]},
            {self.usd.id, eur.id},
        )

        payment = self._create_payment(invoice, eur, 80.0, self.rate_date_invoice)
        self.assertAlmostEqual(payment.amount_local, 100.0, places=2)
        self.assertAlmostEqual(payment.amount_ref, 80.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual_secondary_currency, 0.0, places=2)

    def test_dependencies_do_not_require_venezuelan_localization(self):
        self.assertTrue(self.ves.active)
        self.assertEqual(self.company.country_id, self.env.ref("base.de"))

        module = self.env["ir.module.module"].search(
            [("name", "=", "accounting_dual_currency")],
            limit=1,
        )
        dependencies = set(module.dependencies_id.mapped("name"))
        self.assertNotIn("l10n_ve", dependencies)
        self.assertNotIn("l10n_ve_full", dependencies)
        self.assertIn("account_reports", dependencies)
        self.assertNotIn("account_report_multi_currency", dependencies)

    def _create_stated_rate_entry(self, entry_date=None):
        """Entry that states 100 USD for 5.280 VES: a rate of 52.8, not the system rate of 50."""
        accounts = self.company_data
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": entry_date or self.rate_date_invoice,
                "line_ids": [
                    Command.create(
                        {
                            "name": "USD debit",
                            "account_id": accounts["default_account_expense"].id,
                            "currency_id": self.usd.id,
                            "amount_currency": 100.0,
                            "balance": 5280.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "USD credit",
                            "account_id": accounts["default_account_revenue"].id,
                            "currency_id": self.usd.id,
                            "amount_currency": -100.0,
                            "balance": -5280.0,
                        }
                    ),
                ],
            }
        )
        entry.action_post()
        return entry

    def test_entry_items_in_the_reference_currency_keep_their_own_amount(self):
        entry = self._create_stated_rate_entry()
        debit_item, credit_item = entry.line_ids.sorted("id")
        self.assertAlmostEqual(debit_item.balance, 5280.0)
        # The reference amount is the amount in currency, not 5.280 / 50 of the date.
        self.assertAlmostEqual(debit_item.balance_secondary_currency, 100.0)
        self.assertAlmostEqual(debit_item.debit_secondary_currency, 100.0)
        self.assertAlmostEqual(debit_item.credit_secondary_currency, 0.0)
        self.assertAlmostEqual(credit_item.balance_secondary_currency, -100.0)
        self.assertAlmostEqual(credit_item.credit_secondary_currency, 100.0)
        # The rate of the item is the one it states.
        self.assertAlmostEqual(debit_item.conversion_rate, 52.8)
        self.assertAlmostEqual(credit_item.conversion_rate, 52.8)

    def test_reversal_of_an_entry_cancels_its_reference_amounts_at_any_date(self):
        entry = self._create_stated_rate_entry()
        reversal = self._create_credit_note(entry, self.rate_date_third)
        for item, original in zip(
            reversal.line_ids.sorted("id"), entry.line_ids.sorted("id")
        ):
            self.assertAlmostEqual(item.balance, -original.balance)
            self.assertAlmostEqual(
                item.balance_secondary_currency, -original.balance_secondary_currency
            )

    def test_entry_items_without_an_amount_in_currency_keep_converting_the_balance(self):
        accounts = self.company_data
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.misc_journal.id,
                "date": self.rate_date_invoice,
                "line_ids": [
                    # Like the exchange difference items: a balance without amount in currency.
                    Command.create(
                        {
                            "name": "Exchange difference",
                            "account_id": accounts["default_account_expense"].id,
                            "currency_id": self.usd.id,
                            "amount_currency": 0.0,
                            "balance": 52.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Company currency item",
                            "account_id": accounts["default_account_revenue"].id,
                            "currency_id": self.ves.id,
                            "amount_currency": -52.0,
                            "balance": -52.0,
                        }
                    ),
                ],
            }
        )
        entry.action_post()
        exchange_item, company_item = entry.line_ids.sorted("id")
        self.assertAlmostEqual(exchange_item.balance_secondary_currency, 52.0 / 50.0)
        self.assertAlmostEqual(exchange_item.conversion_rate, 50.0)
        self.assertAlmostEqual(company_item.balance_secondary_currency, -52.0 / 50.0)

    def test_invoice_items_keep_converting_the_balance_at_the_rate_of_the_invoice(self):
        invoice = self._create_invoice(self.usd, 100.0, self.rate_date_invoice)
        receivable = self._get_payment_term_line(invoice)
        self.assertEqual(receivable.currency_id, self.usd)
        self.assertFalse(receivable._has_own_reference_amount())
        self.assertAlmostEqual(receivable.conversion_rate, 50.0)
        self.assertAlmostEqual(receivable.balance_secondary_currency, 100.0)
