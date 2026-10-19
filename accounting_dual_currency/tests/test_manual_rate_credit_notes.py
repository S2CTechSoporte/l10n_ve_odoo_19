from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRateCreditNotes(DualCurrencyTestCommon):
    """Credit notes keep the manual rate of the document they reverse."""

    def _exchange_moves(self, invoice):
        partials = invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids
        return partials.exchange_move_id

    def test_credit_note_of_a_usd_bill_keeps_the_manual_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        credit_note = self._create_credit_note(bill, self.rate_date_third)
        payable = self._get_payment_term_line(credit_note)

        self.assertEqual(credit_note.move_type, "in_refund")
        self.assertTrue(credit_note.manual_rate_active)
        self.assertAlmostEqual(credit_note.manual_conversion_rate, 60.0)
        self.assertAlmostEqual(credit_note.invoice_currency_rate, 1 / 60.0)
        self.assertAlmostEqual(payable.debit, 6000.0)
        self.assertAlmostEqual(credit_note.amount_total_local_currency, 6000.0)
        self.assertAlmostEqual(credit_note.amount_total_secondary_currency, 100.0)
        self.assertAlmostEqual(credit_note.conversion_rate, 60.0)
        self.assertAlmostEqual(abs(payable.balance_secondary_currency), 100.0)

    def test_credit_note_of_a_usd_bill_cancels_it_without_exchange_difference(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        # Posting a credit note reconciles it with the invoice it reverses.
        credit_note = self._create_credit_note(bill, self.rate_date_third)

        self.assertEqual(bill.payment_state, "reversed")
        self.assertTrue(bill.currency_id.is_zero(bill.amount_residual))
        self.assertAlmostEqual(bill.amount_residual_secondary_currency, 0.0)
        self.assertTrue(bill.line_ids.matched_debit_ids)
        self.assertFalse(self._exchange_moves(bill))

    def test_credit_note_of_a_company_currency_bill_keeps_the_manual_rate(self):
        bill = self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        credit_note = self._create_credit_note(bill, self.rate_date_third)
        payable = self._get_payment_term_line(credit_note)

        self.assertTrue(credit_note.manual_rate_active)
        self.assertAlmostEqual(credit_note.manual_conversion_rate, 60.0)
        self.assertAlmostEqual(payable.debit, 6000.0)
        self.assertAlmostEqual(credit_note.amount_total_local_currency, 6000.0)
        # 6000 / 60, not 6000 / 50 (date of the bill) nor 6000 / 54 (date of the note)
        self.assertAlmostEqual(credit_note.amount_total_secondary_currency, 100.0)
        self.assertAlmostEqual(credit_note.conversion_rate, 60.0)
        self.assertAlmostEqual(abs(payable.balance_secondary_currency), 100.0)

    def test_credit_note_of_a_system_rate_bill_has_no_manual_rate(self):
        bill = self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "in_invoice"
        )
        credit_note = self._create_credit_note(bill, self.rate_date_third)
        self.assertFalse(credit_note.manual_rate)
        self.assertEqual(credit_note.manual_conversion_rate, 0.0)
        self.assertAlmostEqual(credit_note.conversion_rate, 50.0)

    def test_credit_note_of_a_customer_invoice_keeps_the_manual_rate(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        credit_note = self._create_credit_note(invoice, self.rate_date_third)
        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertTrue(credit_note.manual_rate_active)
        self.assertAlmostEqual(credit_note.invoice_currency_rate, 1 / 60.0)
        self.assertAlmostEqual(
            self._get_payment_term_line(credit_note).credit, 6000.0
        )
