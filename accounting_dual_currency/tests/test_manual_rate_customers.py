from odoo import Command
from odoo.tests import Form, tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRateCustomers(DualCurrencyTestCommon):
    """The manual rate on customer documents: invoices, receipts, payments and wizard."""

    def _create_draft_customer_document(self, move_type, **values):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "invoice_date": self.rate_date_invoice,
                "date": self.rate_date_invoice,
                "partner_id": self.partner_customer.id,
                "journal_id": self.sale_journal.id,
                "currency_id": self.usd.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
                **values,
            }
        )

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

    # ---------------------------------------------------------------- documents

    def test_every_customer_document_type_offers_the_manual_rate(self):
        for move_type, sign in (("out_invoice", 1), ("out_refund", -1), ("out_receipt", 1)):
            with self.subTest(move_type=move_type):
                document = self._create_draft_customer_document(move_type)
                self.assertTrue(document.manual_rate_available)
                document.write({"manual_rate": True, "manual_conversion_rate": 60.0})
                self.assertTrue(document.manual_rate_active)
                self.assertAlmostEqual(document.invoice_currency_rate, 1 / 60.0)
                self.assertAlmostEqual(
                    self._get_payment_term_line(document).balance, sign * 6000.0
                )

    def test_customer_invoice_form_defaults_the_manual_rate_to_the_system_rate(self):
        form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        form.partner_id = self.partner_customer
        form.invoice_date = self.rate_date_invoice
        form.currency_id = self.usd
        with form.invoice_line_ids.new() as line:
            line.product_id = self.product
            line.price_unit = 100.0
        self.assertFalse(form.manual_rate)
        form.manual_rate = True
        self.assertAlmostEqual(form.manual_conversion_rate, 50.0)
        form.manual_conversion_rate = 60.0
        self.assertAlmostEqual(form.invoice_currency_rate, 1 / 60.0)
        invoice = form.save()
        self.assertTrue(invoice.manual_rate_active)
        self.assertAlmostEqual(self._get_payment_term_line(invoice).debit, 6000.0)

    def test_customer_invoice_form_resets_the_manual_rate_when_the_currency_is_not_available(self):
        gbp = self.env.ref("base.GBP")
        gbp.active = True
        self._set_rate(gbp, self.company, self.rate_date_invoice, 40.0)
        form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        form.partner_id = self.partner_customer
        form.invoice_date = self.rate_date_invoice
        form.currency_id = self.usd
        form.manual_rate = True
        form.manual_conversion_rate = 60.0
        form.currency_id = gbp
        self.assertFalse(form.manual_rate)

    def test_customer_invoice_in_company_currency_uses_the_manual_rate_for_the_reference_amounts(self):
        invoice = self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        receivable = self._get_payment_term_line(invoice)
        self.assertAlmostEqual(receivable.debit, 6000.0)
        self.assertAlmostEqual(invoice.amount_total_secondary_currency, 100.0)
        self.assertAlmostEqual(receivable.balance_secondary_currency, 100.0)

    # ----------------------------------------------------------------- payments

    def test_customer_payment_form_defaults_the_manual_rate_to_the_system_rate(self):
        form = Form(
            self.env["account.payment"].with_context(
                default_payment_type="inbound", default_partner_type="customer"
            )
        )
        form.partner_id = self.partner_customer
        form.amount = 100.0
        form.currency_id = self.usd
        form.date = self.rate_date_second
        self.assertFalse(form.manual_rate)
        form.manual_rate = True
        self.assertAlmostEqual(form.manual_conversion_rate, 52.0)
        form.manual_conversion_rate = 60.0
        self.assertAlmostEqual(form.conversion_rate_display, 60.0)
        payment = form.save()
        self.assertEqual(payment.payment_type, "inbound")
        self.assertTrue(payment.manual_rate)
        self.assertAlmostEqual(payment.manual_conversion_rate, 60.0)
        payment.action_post()
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, 6000.0)
        self.assertTrue(payment.move_id.manual_rate)

    def test_customer_wizard_offers_and_applies_the_manual_rate(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        wizard = self._wizard(
            invoice,
            currency_id=self.ves.id,
            manual_rate=True,
            manual_conversion_rate=60.0,
        )
        self.assertEqual(wizard.partner_type, "customer")
        self.assertTrue(wizard.manual_rate_available)
        self.assertTrue(wizard.manual_rate_active)
        self.assertAlmostEqual(wizard.amount, 6000.0)
        self.assertAlmostEqual(wizard.payment_difference, 0.0)

        payment = wizard._create_payments()
        self.assertEqual(payment.payment_type, "inbound")
        self.assertTrue(payment.manual_rate)
        self.assertAlmostEqual(payment.manual_conversion_rate, 60.0)
        self.assertTrue(payment.move_id.manual_rate)
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, 6000.0)
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

    def test_customer_wizard_form_defaults_the_manual_rate_to_the_system_rate(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice"
        )
        form = Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=invoice.ids
            )
        )
        form.payment_date = self.rate_date_third
        self.assertFalse(form.manual_rate)
        form.manual_rate = True
        self.assertAlmostEqual(form.manual_conversion_rate, 54.0)

    def test_customer_payment_at_the_invoice_rate_settles_it_without_exchange_difference(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        payment = self._create_payment(
            invoice, self.usd, 100.0, self.rate_date_second, manual_rate=60.0
        )
        self.assertTrue(payment.manual_rate_active)
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self.assertFalse(self._exchange_moves(invoice))
        self.assertAlmostEqual(invoice.amount_residual_secondary_currency, 0.0)

    def test_customer_payment_without_manual_rate_settles_a_manual_rate_invoice_with_an_exchange_difference(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        payment = self._create_payment(invoice, self.usd, 100.0, self.rate_date_second)
        self.assertFalse(payment.manual_rate)
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, 5200.0)
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self.assertAlmostEqual(
            sum(self._exchange_moves(invoice).line_ids.mapped("debit")), 800.0, places=2
        )

    def test_customer_credit_note_of_a_manual_rate_invoice_cancels_it(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        credit_note = self._create_credit_note(invoice, self.rate_date_third)
        self.assertTrue(credit_note.manual_rate_active)
        self.assertEqual(invoice.payment_state, "reversed")
        self.assertFalse(self._exchange_moves(invoice))
        self.assertAlmostEqual(invoice.amount_residual_secondary_currency, 0.0)
