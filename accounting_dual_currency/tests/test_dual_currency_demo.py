from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDualCurrencyDemo(TransactionCase):
    def test_secondary_currency_default_depends_on_company_currency(self):
        company_model = self.env["res.company"]
        currencies = {
            "EUR": self.env.ref("base.EUR"),
            "GBP": self.env.ref("base.GBP"),
            "USD": self.env.ref("base.USD"),
        }

        for code, currency in currencies.items():
            company = company_model.create(
                {"name": f"Default Currency {code}", "currency_id": currency.id}
            )
            defaults = company_model.with_company(company).default_get(
                ["secondary_currency_id"]
            )
            expected_currency = (
                self.env.ref("base.USD")
                if code != "USD"
                else False
            )
            self.assertEqual(
                defaults.get("secondary_currency_id"), expected_currency.id if expected_currency else False
            )

    def test_demo_company_and_rate(self):
        company = self.env.ref(
            "accounting_dual_currency.demo_company_eur",
            raise_if_not_found=False,
        )
        if not company:
            self.skipTest("The database was initialized without demo data.")

        rate = self.env.ref("accounting_dual_currency.demo_rate_usd_20260110")
        self.assertEqual(company.country_id, self.env.ref("base.de"))
        self.assertEqual(company.currency_id, self.env.ref("base.EUR"))
        self.assertEqual(company.secondary_currency_id, self.env.ref("base.USD"))
        self.assertEqual(rate.company_id, company)
        self.assertEqual(rate.currency_id, self.env.ref("base.USD"))
        self.assertAlmostEqual(rate.rate, 1.25, places=8)
