from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestDualCurrencyInvoicePayments(DualCurrencyTestCommon):
    def test_invoice_usd_full_payment_usd(self):
        self._run_invoice_payment_scenario(
            self.usd,
            100.0,
            [
                {
                    "currency": self.usd,
                    "amount": 100.0,
                    "date": self.rate_date_invoice,
                }
            ],
        )

    def test_invoice_usd_full_payment_ves(self):
        self._run_invoice_payment_scenario(
            self.usd,
            100.0,
            [
                {
                    "currency": self.ves,
                    "amount": 5000.0,
                    "date": self.rate_date_invoice,
                }
            ],
        )

    def test_invoice_ves_full_payment_usd(self):
        self._run_invoice_payment_scenario(
            self.ves,
            5000.0,
            [
                {
                    "currency": self.usd,
                    "amount": 100.0,
                    "date": self.rate_date_invoice,
                }
            ],
        )

    def test_invoice_ves_full_payment_ves(self):
        self._run_invoice_payment_scenario(
            self.ves,
            5000.0,
            [
                {
                    "currency": self.ves,
                    "amount": 5000.0,
                    "date": self.rate_date_invoice,
                }
            ],
        )

    def test_invoice_usd_partial_payments_usd(self):
        self._run_invoice_payment_scenario(
            self.usd,
            100.0,
            [
                {
                    "currency": self.usd,
                    "amount": 40.0,
                    "date": self.rate_date_invoice,
                },
                {
                    "currency": self.usd,
                    "amount": 60.0,
                    "date": self.rate_date_invoice,
                },
            ],
        )

    def test_invoice_usd_partial_payments_ves(self):
        self._run_invoice_payment_scenario(
            self.usd,
            100.0,
            [
                {
                    "currency": self.ves,
                    "amount": 2000.0,
                    "date": self.rate_date_invoice,
                },
                {
                    "currency": self.ves,
                    "amount": 3000.0,
                    "date": self.rate_date_invoice,
                },
            ],
        )

    def test_invoice_usd_mixed_partial_payments_multi_date(self):
        self._run_invoice_payment_scenario(
            self.usd,
            100.0,
            [
                {
                    "currency": self.usd,
                    "amount": 30.0,
                    "date": self.rate_date_invoice,
                },
                {
                    "currency": self.ves,
                    "amount": 2080.0,
                    "date": self.rate_date_second,
                },
                {
                    "currency": self.usd,
                    "amount": 30.0,
                    "date": self.rate_date_third,
                },
            ],
        )

    def test_invoice_ves_partial_payments_usd(self):
        self._run_invoice_payment_scenario(
            self.ves,
            5000.0,
            [
                {
                    "currency": self.usd,
                    "amount": 25.0,
                    "date": self.rate_date_invoice,
                },
                {
                    "currency": self.usd,
                    "amount": 75.0,
                    "date": self.rate_date_invoice,
                },
            ],
        )

    def test_invoice_ves_partial_payments_ves(self):
        self._run_invoice_payment_scenario(
            self.ves,
            5000.0,
            [
                {
                    "currency": self.ves,
                    "amount": 2000.0,
                    "date": self.rate_date_invoice,
                },
                {
                    "currency": self.ves,
                    "amount": 3000.0,
                    "date": self.rate_date_invoice,
                },
            ],
        )

    def test_invoice_ves_mixed_partial_payments_multi_date(self):
        self._run_invoice_payment_scenario(
            self.ves,
            5000.0,
            [
                {
                    "currency": self.usd,
                    "amount": 25.0,
                    "date": self.rate_date_invoice,
                },
                {
                    "currency": self.ves,
                    "amount": 1050.0,
                    "date": self.rate_date_second,
                },
                {
                    "currency": self.usd,
                    "amount": 50.0,
                    "date": self.rate_date_third,
                },
            ],
        )

    def test_manual_rate_context_does_not_change_dual_amounts(self):
        payment = self.env["account.payment"].with_context(
            manual_rate=999.0
        ).create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "amount": 5000.0,
                "date": self.rate_date_invoice,
                "currency_id": self.ves.id,
                "journal_id": self.bank_journal.id,
                "partner_id": self.partner_customer.id,
            }
        )
        self.assertAlmostEqual(payment.amount_local, 5000.0, places=2)
        self.assertAlmostEqual(payment.amount_ref, 100.0, places=2)
        self.assertAlmostEqual(payment.conversion_rate, 50.0, places=2)
