from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRateInvoicePayments(DualCurrencyTestCommon):
    """The mandatory invoice and payment matrix, converted at manual rates.

    The manual rates (60, 62 and 64 CCY per USD) differ from the system rates of the
    same dates (50, 52 and 54), so any amount converted with the system rate fails.
    The matrix runs for vendor bills (the default use of the manual rate) and for
    customer invoices, because the model logic does not depend on the document side.
    """

    manual_rate_invoice = 60.0
    manual_rate_second = 62.0
    manual_rate_third = 64.0

    def _payment(self, currency, amount, payment_date=None, manual_rate=None):
        return {
            "currency": currency,
            "amount": amount,
            "date": payment_date or self.rate_date_invoice,
            "manual_rate": manual_rate or self.manual_rate_invoice,
        }

    def _run_manual_scenario(self, invoice_currency, invoice_amount, payments):
        for move_type in ("in_invoice", "out_invoice"):
            with self.subTest(move_type=move_type):
                invoice = self._run_invoice_payment_scenario(
                    invoice_currency,
                    invoice_amount,
                    payments,
                    invoice_manual_rate=self.manual_rate_invoice,
                    move_type=move_type,
                )
                self.assertTrue(invoice.manual_rate)
                self.assertAlmostEqual(
                    invoice.manual_conversion_rate, self.manual_rate_invoice
                )

    def test_manual_invoice_usd_full_payment_usd(self):
        self._run_manual_scenario(self.usd, 100.0, [self._payment(self.usd, 100.0)])

    def test_manual_invoice_usd_full_payment_ves(self):
        self._run_manual_scenario(self.usd, 100.0, [self._payment(self.ves, 6000.0)])

    def test_manual_invoice_ves_full_payment_usd(self):
        self._run_manual_scenario(self.ves, 6000.0, [self._payment(self.usd, 100.0)])

    def test_manual_invoice_ves_full_payment_ves(self):
        self._run_manual_scenario(self.ves, 6000.0, [self._payment(self.ves, 6000.0)])

    def test_manual_invoice_usd_partial_payments_usd(self):
        self._run_manual_scenario(
            self.usd,
            100.0,
            [self._payment(self.usd, 40.0), self._payment(self.usd, 60.0)],
        )

    def test_manual_invoice_usd_partial_payments_ves(self):
        self._run_manual_scenario(
            self.usd,
            100.0,
            [self._payment(self.ves, 2400.0), self._payment(self.ves, 3600.0)],
        )

    def test_manual_invoice_usd_mixed_partial_payments_multi_date(self):
        self._run_manual_scenario(
            self.usd,
            100.0,
            [
                self._payment(self.usd, 30.0),
                self._payment(
                    self.ves, 2480.0, self.rate_date_second, self.manual_rate_second
                ),
                self._payment(
                    self.usd, 30.0, self.rate_date_third, self.manual_rate_third
                ),
            ],
        )

    def test_manual_invoice_ves_partial_payments_usd(self):
        self._run_manual_scenario(
            self.ves,
            6000.0,
            [self._payment(self.usd, 25.0), self._payment(self.usd, 75.0)],
        )

    def test_manual_invoice_ves_partial_payments_ves(self):
        self._run_manual_scenario(
            self.ves,
            6000.0,
            [self._payment(self.ves, 2400.0), self._payment(self.ves, 3600.0)],
        )

    def test_manual_invoice_ves_mixed_partial_payments_multi_date(self):
        self._run_manual_scenario(
            self.ves,
            6000.0,
            [
                self._payment(self.usd, 25.0),
                self._payment(
                    self.ves, 1300.0, self.rate_date_second, self.manual_rate_second
                ),
                self._payment(
                    self.usd, 50.0, self.rate_date_third, self.manual_rate_third
                ),
            ],
        )
