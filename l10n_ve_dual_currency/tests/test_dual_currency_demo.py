from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDualCurrencyDemo(TransactionCase):
    def test_venezuelan_demo_company_and_rate(self):
        company = self.env.ref(
            "l10n_ve_dual_currency.demo_company_ves",
            raise_if_not_found=False,
        )
        if not company:
            self.skipTest("The database was initialized without demo data.")

        rate = self.env.ref("l10n_ve_dual_currency.demo_rate_usd_20260110")
        self.assertEqual(company.country_id, self.env.ref("base.ve"))
        self.assertEqual(company.currency_id, self.env.ref("base.VES"))
        self.assertEqual(company.fcurrency_id, self.env.ref("base.USD"))
        self.assertEqual(rate.company_id, company)
        self.assertEqual(rate.currency_id, self.env.ref("base.USD"))
        self.assertAlmostEqual(rate.rate, 0.02, places=8)
