from odoo import Command
from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRateDemo(DualCurrencyTestCommon):
    """Manual rate on the EUR/USD demo company (skipped without demo data)."""

    def _create_bill(self, company, journal, account, manual_rate=None):
        values = {
            "move_type": "in_invoice",
            "company_id": company.id,
            "journal_id": journal.id,
            "partner_id": self.partner_vendor.id,
            "invoice_date": self.rate_date_invoice,
            "date": self.rate_date_invoice,
            "currency_id": self.usd.id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "Demo manual rate service",
                        "account_id": account.id,
                        "quantity": 1.0,
                        "price_unit": 100.0,
                        "tax_ids": [Command.clear()],
                    }
                )
            ],
        }
        if manual_rate:
            values.update({"manual_rate": True, "manual_conversion_rate": manual_rate})
        bill = self.env["account.move"].with_company(company).create(values)
        bill.action_post()
        return bill

    def test_demo_company_converts_a_usd_bill_at_the_manual_rate(self):
        company = self.env.ref(
            "accounting_dual_currency.demo_company_eur", raise_if_not_found=False
        )
        if not company:
            self.skipTest("The database was initialized without demo data.")
        self.env.user.sudo().write({"company_ids": [Command.link(company.id)]})
        self.env["account.chart.template"].with_company(company).try_loading(
            "generic_coa", company=company, install_demo=False
        )
        # The generic chart sets the currency of the company; the demo data declares EUR.
        company.currency_id = self.env.ref("base.EUR")
        self.assertEqual(company.secondary_currency_id, self.usd)
        journal = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "purchase")], limit=1
        )
        account = self.env["account.account"].search(
            [
                ("company_ids", "in", company.ids),
                ("account_type", "=", "expense"),
            ],
            limit=1,
        )
        system_bill = self._create_bill(company, journal, account)
        manual_bill = self._create_bill(company, journal, account, manual_rate=0.9)

        # 1 EUR = 1.25 USD in the demo rate, that is 0.8 EUR per USD.
        self.assertFalse(system_bill.manual_rate_active)
        self.assertAlmostEqual(self._get_payment_term_line(system_bill).credit, 80.0)
        self.assertAlmostEqual(system_bill.conversion_rate_display, 0.8)

        self.assertTrue(manual_bill.manual_rate_active)
        self.assertTrue(manual_bill.manual_rate_is_usd)
        self.assertEqual(manual_bill.manual_rate_currency_id, self.env.ref("base.EUR"))
        self.assertAlmostEqual(manual_bill.invoice_currency_rate, 1 / 0.9)
        self.assertAlmostEqual(self._get_payment_term_line(manual_bill).credit, 90.0)
        self.assertAlmostEqual(manual_bill.conversion_rate_display, 0.9)
        self.assertEqual(
            manual_bill.conversion_rate_display_currency_id, self.env.ref("base.EUR")
        )
        self.assertAlmostEqual(manual_bill.amount_total_secondary_currency, 100.0)
        self.assertAlmostEqual(manual_bill.amount_total_local_currency, 90.0)
