from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRatePayments(DualCurrencyTestCommon):
    """Payments and the register payment wizard converted at the manual rate."""

    def _wizard(self, invoices, **values):
        return self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoices.ids,
        ).create(
            {
                "payment_date": self.rate_date_invoice,
                "journal_id": self.bank_journal.id,
                **values,
            }
        )

    def _exchange_moves(self, invoice):
        partials = invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids
        return partials.exchange_move_id

    # ---------------------------------------------------------- payment model

    def test_payment_converts_the_journal_items_at_the_manual_rate(self):
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, manual_rate=60.0
        )
        liquidity, counterpart, _writeoff = payment._seek_for_lines()
        move = payment.move_id

        self.assertTrue(payment.manual_rate_active)
        self.assertAlmostEqual(liquidity.balance, -6000.0)
        self.assertAlmostEqual(liquidity.credit, 6000.0)
        self.assertAlmostEqual(liquidity.amount_currency, -100.0)
        self.assertAlmostEqual(counterpart.balance, 6000.0)
        self.assertAlmostEqual(counterpart.debit, 6000.0)
        self.assertAlmostEqual(payment.amount_local, 6000.0)
        self.assertAlmostEqual(payment.amount_ref, 100.0)
        self.assertAlmostEqual(payment.conversion_rate, 60.0)
        self.assertAlmostEqual(payment.conversion_rate_display, 60.0)
        self.assertEqual(payment.conversion_rate_display_currency_id, self.ves)
        self.assertAlmostEqual(payment.amount_company_currency_signed, -6000.0)
        # The journal entry of the payment carries the rate to its journal items.
        self.assertTrue(move.manual_rate)
        self.assertAlmostEqual(move.manual_conversion_rate, 60.0)
        self.assertAlmostEqual(move.conversion_rate, 60.0)
        self.assertAlmostEqual(liquidity.conversion_rate, 60.0)
        self.assertAlmostEqual(liquidity.balance_secondary_currency, -100.0)
        self.assertAlmostEqual(counterpart.debit_secondary_currency, 100.0)

    def test_payment_without_manual_rate_keeps_the_system_rate(self):
        payment = self._create_direct_payment(self.usd, 100.0, self.rate_date_invoice)
        liquidity, counterpart, _writeoff = payment._seek_for_lines()
        self.assertFalse(payment.manual_rate)
        self.assertFalse(payment.move_id.manual_rate)
        self.assertEqual(payment.move_id.manual_conversion_rate, 0.0)
        self.assertAlmostEqual(liquidity.balance, -5000.0)
        self.assertAlmostEqual(counterpart.balance, 5000.0)
        self.assertAlmostEqual(payment.amount_local, 5000.0)
        self.assertAlmostEqual(payment.conversion_rate, 50.0)

    def test_payment_in_company_currency_uses_the_manual_rate_for_the_reference_amount(self):
        payment = self._create_direct_payment(
            self.ves, 6000.0, self.rate_date_invoice, manual_rate=60.0
        )
        liquidity, _counterpart, _writeoff = payment._seek_for_lines()
        self.assertAlmostEqual(liquidity.balance, -6000.0)
        self.assertAlmostEqual(payment.amount_local, 6000.0)
        self.assertAlmostEqual(payment.amount_ref, 100.0)
        self.assertAlmostEqual(liquidity.balance_secondary_currency, -100.0)

    def test_draft_payment_follows_the_manual_rate_changes(self):
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, manual_rate=60.0
        )
        payment.action_draft()
        liquidity, counterpart, _writeoff = payment._seek_for_lines()
        self.assertEqual(payment.state, "draft")

        payment.manual_conversion_rate = 62.0
        self.assertAlmostEqual(liquidity.balance, -6200.0)
        self.assertAlmostEqual(counterpart.balance, 6200.0)
        self.assertAlmostEqual(payment.move_id.manual_conversion_rate, 62.0)
        self.assertAlmostEqual(payment.amount_local, 6200.0)

        payment.manual_rate = False
        self.assertAlmostEqual(liquidity.balance, -5000.0)
        self.assertFalse(payment.move_id.manual_rate)
        self.assertEqual(payment.move_id.manual_conversion_rate, 0.0)

        payment.write({"manual_rate": True, "manual_conversion_rate": 64.0})
        payment.action_post()
        self.assertAlmostEqual(liquidity.balance, -6400.0)
        self.assertTrue(payment.move_id.manual_rate)
        self.assertAlmostEqual(payment.move_id.manual_conversion_rate, 64.0)

    def test_manual_rate_of_a_payment_that_is_not_in_draft_cannot_be_modified(self):
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, manual_rate=60.0
        )
        self.assertEqual(payment.state, "in_process")
        with self._assert_error(UserError, "cannot modify the manual rate"):
            payment.manual_conversion_rate = 62.0
        with self._assert_error(UserError, "cannot modify the manual rate"):
            payment.manual_rate = False
        payment.write({"manual_rate": True, "manual_conversion_rate": 60.0})
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, -6000.0)

    def test_payment_manual_rate_is_validated(self):
        gbp = self.env.ref("base.GBP")
        gbp.active = True
        self._set_rate(gbp, self.company, self.rate_date_invoice, 40.0)
        with self._assert_error(ValidationError, "manual rate is only available"):
            self._create_direct_payment(
                gbp, 100.0, self.rate_date_invoice, manual_rate=40.0, post=False
            )
        for rate in (0.0, -60.0):
            with self.subTest(rate=rate):
                with self._assert_error(ValidationError, "strictly positive"):
                    self.env["account.payment"].create(
                        {
                            "payment_type": "outbound",
                            "partner_type": "supplier",
                            "partner_id": self.partner_vendor.id,
                            "amount": 100.0,
                            "date": self.rate_date_invoice,
                            "currency_id": self.usd.id,
                            "journal_id": self.bank_journal.id,
                            "manual_rate": True,
                            "manual_conversion_rate": rate,
                        }
                    )

    # ----------------------------------------------------------------- wizard

    def test_wizard_default_amount_uses_the_manual_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        system_wizard = self._wizard(bill, currency_id=self.ves.id)
        self.assertFalse(system_wizard.manual_rate_active)
        self.assertAlmostEqual(system_wizard.amount, 5000.0)
        self.assertAlmostEqual(system_wizard.payment_difference, 0.0)

        manual_wizard = self._wizard(
            bill,
            currency_id=self.ves.id,
            manual_rate=True,
            manual_conversion_rate=60.0,
        )
        self.assertTrue(manual_wizard.manual_rate_active)
        self.assertAlmostEqual(manual_wizard.amount, 6000.0)
        self.assertAlmostEqual(manual_wizard.payment_difference, 0.0)

    def test_wizard_recomputes_the_amount_when_the_manual_rate_changes(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        wizard = self._wizard(
            bill,
            currency_id=self.ves.id,
            manual_rate=True,
            manual_conversion_rate=60.0,
        )
        self.assertAlmostEqual(wizard.amount, 6000.0)
        wizard.manual_conversion_rate = 65.0
        self.assertAlmostEqual(wizard.amount, 6500.0)
        wizard.manual_rate = False
        self.assertAlmostEqual(wizard.amount, 5000.0)

    def test_wizard_is_only_available_for_a_single_editable_payment(self):
        other_vendor = self.env["res.partner"].create(
            {"name": "Other Dual Currency Vendor", "supplier_rank": 1}
        )
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        other_bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        other_bill.button_draft()
        other_bill.partner_id = other_vendor
        other_bill.action_post()

        gbp = self.env.ref("base.GBP")
        gbp.active = True
        self.assertTrue(self._wizard(bill).manual_rate_available)
        self.assertFalse(
            self._wizard(bill + other_bill).manual_rate_available,
            "Several payments cannot share one manual rate",
        )
        self.assertFalse(self._wizard(bill, currency_id=gbp.id).manual_rate_available)

    def test_wizard_creates_the_payment_with_the_manual_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        wizard = self._wizard(
            bill,
            currency_id=self.usd.id,
            manual_rate=True,
            manual_conversion_rate=60.0,
        )
        payment = wizard._create_payments()
        liquidity, _counterpart, _writeoff = payment._seek_for_lines()

        self.assertTrue(payment.manual_rate)
        self.assertAlmostEqual(payment.manual_conversion_rate, 60.0)
        self.assertTrue(payment.move_id.manual_rate)
        self.assertAlmostEqual(liquidity.balance, -6000.0)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertFalse(self._exchange_moves(bill))

    def test_wizard_without_manual_rate_creates_a_system_rate_payment(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        payment = self._wizard(bill, currency_id=self.usd.id)._create_payments()
        self.assertFalse(payment.manual_rate)
        self.assertEqual(payment.manual_conversion_rate, 0.0)
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, -5000.0)

    # --------------------------------------------------------- reconciliation

    def test_payment_rate_different_from_the_bill_rate_creates_an_exchange_difference(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        payment = self._create_payment(
            bill, self.usd, 100.0, self.rate_date_invoice, manual_rate=62.0
        )
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, -6200.0)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertTrue(bill.currency_id.is_zero(bill.amount_residual))
        self.assertAlmostEqual(bill.amount_residual_secondary_currency, 0.0)
        exchange_move = self._exchange_moves(bill)
        self.assertEqual(len(exchange_move), 1)
        self.assertAlmostEqual(
            sum(exchange_move.line_ids.mapped("debit")), 200.0, places=2
        )

    def test_manual_payment_does_not_change_the_amounts_of_a_system_rate_bill(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        self._create_payment(
            bill, self.usd, 100.0, self.rate_date_invoice, manual_rate=60.0
        )
        payable = self._get_payment_term_line(bill)
        self.assertAlmostEqual(bill.amount_total_local_currency, 5000.0)
        self.assertAlmostEqual(bill.amount_total_secondary_currency, 100.0)
        self.assertAlmostEqual(bill.invoice_currency_rate, 1 / 50.0)
        self.assertAlmostEqual(bill.conversion_rate, 50.0)
        self.assertAlmostEqual(payable.credit, 5000.0)
        self.assertAlmostEqual(payable.balance_secondary_currency, -100.0)
        self.assertAlmostEqual(payable.conversion_rate, 50.0)
        self.assertAlmostEqual(bill.amount_residual_secondary_currency, 0.0)
        self.assertAlmostEqual(
            sum(self._exchange_moves(bill).line_ids.mapped("debit")), 1000.0, places=2
        )

    def test_system_rate_payment_settles_a_manual_rate_bill(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        payment = self._create_payment(bill, self.usd, 100.0, self.rate_date_second)
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, -5200.0)
        self.assertFalse(payment.move_id.manual_rate)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertAlmostEqual(bill.amount_residual_secondary_currency, 0.0)
        self.assertAlmostEqual(
            sum(self._exchange_moves(bill).line_ids.mapped("debit")), 800.0, places=2
        )

    def test_outstanding_company_currency_payment_is_applied_at_its_manual_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        payment = self._create_direct_payment(
            self.ves, 3000.0, self.rate_date_invoice, manual_rate=60.0
        )
        bill.js_assign_outstanding_line(payment._seek_for_lines()[1].id)

        # 3000 / 60 = 50 USD; at the system rate it would be 3000 / 50 = 60 USD.
        self.assertEqual(bill.payment_state, "partial")
        self.assertAlmostEqual(bill.amount_residual, 50.0)
        self.assertAlmostEqual(bill.amount_residual_secondary_currency, 50.0)

    def test_outstanding_company_currency_payment_without_manual_rate_uses_the_system_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        payment = self._create_direct_payment(self.ves, 3000.0, self.rate_date_invoice)
        bill.js_assign_outstanding_line(payment._seek_for_lines()[1].id)
        self.assertAlmostEqual(bill.amount_residual, 40.0)
        self.assertAlmostEqual(bill.amount_residual_secondary_currency, 40.0)

    def test_outstanding_widget_shows_company_currency_payments_at_their_manual_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        manual_payment = self._create_direct_payment(
            self.ves, 3000.0, self.rate_date_invoice, manual_rate=60.0
        )
        system_payment = self._create_direct_payment(
            self.ves, 3000.0, self.rate_date_invoice
        )
        bill.invalidate_recordset(["invoice_outstanding_credits_debits_widget"])
        amounts = {
            item["move_id"]: item["amount"]
            for item in bill.invoice_outstanding_credits_debits_widget["content"]
        }
        # 3000 / 60 at the manual rate of the payment, 3000 / 50 at the system rate.
        self.assertAlmostEqual(amounts[manual_payment.move_id.id], 50.0)
        self.assertAlmostEqual(amounts[system_payment.move_id.id], 60.0)

    def test_payment_widget_converts_each_payment_at_its_own_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        # Both payments settle 50 USD: one at the manual rate of 60, the other at the
        # system rate of 54 of its date. At the manual rate of the bill, the second
        # payment would be worth 45 USD.
        self._create_payment(
            bill, self.ves, 3000.0, self.rate_date_invoice, manual_rate=60.0
        )
        self._create_payment(bill, self.ves, 2700.0, self.rate_date_third)
        self._assert_payment_widgets(
            bill,
            expected_reference_amounts=[50.0, 50.0],
            expected_local_amounts=[3000.0, 2700.0],
        )

    # ------------------------------------------------------------ forms

    def test_payment_form_defaults_the_manual_rate_to_the_system_rate(self):
        form = Form(
            self.env["account.payment"].with_context(
                default_payment_type="outbound", default_partner_type="supplier"
            )
        )
        form.partner_id = self.partner_vendor
        form.amount = 100.0
        form.currency_id = self.usd
        form.date = self.rate_date_second
        self.assertFalse(form.manual_rate)
        form.manual_rate = True
        # 52 is the system rate of the date of the payment, not the one of the invoice.
        self.assertAlmostEqual(form.manual_conversion_rate, 52.0)
        form.manual_conversion_rate = 60.0
        self.assertAlmostEqual(form.conversion_rate_display, 60.0)
        payment = form.save()
        self.assertTrue(payment.manual_rate)
        self.assertAlmostEqual(payment.manual_conversion_rate, 60.0)

    def test_wizard_form_defaults_the_manual_rate_to_the_system_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        form = Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=bill.ids
            )
        )
        form.payment_date = self.rate_date_third
        self.assertFalse(form.manual_rate)
        form.manual_rate = True
        self.assertAlmostEqual(form.manual_conversion_rate, 54.0)

    def test_wizard_form_converts_a_custom_amount_at_the_manual_rate_when_the_currency_changes(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        form = Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=bill.ids
            )
        )
        form.payment_date = self.rate_date_invoice
        form.amount = 50.0
        form.manual_rate = True
        form.manual_conversion_rate = 60.0
        form.currency_id = self.ves
        # 50 USD at the manual rate of 60, not at the system rate of 50 (2.500).
        self.assertAlmostEqual(form.amount, 3000.0)
