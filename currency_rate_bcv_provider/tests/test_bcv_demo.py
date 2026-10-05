from datetime import date
from unittest.mock import Mock, patch

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open


REQUEST_TARGET = "odoo.addons.currency_rate_bcv_provider.models.res_company.requests.get"


@tagged("post_install", "-at_install", "bcv_demo")
class TestBCVDemo(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.ref(
            "currency_rate_bcv_provider.demo_company_bcv", raise_if_not_found=False
        )
        if not self.company:
            self.skipTest("The database was initialized without demo data.")
        with file_open(
            "currency_rate_bcv_provider/tests/fixtures/bcv_rates.html", "rb"
        ) as fixture:
            self.response = Mock(content=fixture.read())
        self.response.raise_for_status.return_value = None

    def test_demo_provider_and_sample_rates(self):
        self.assertEqual(self.company.currency_id, self.env.ref("base.USD"))
        self.assertEqual(self.company.country_id, self.env.ref("base.ve"))
        self.assertEqual(self.company.currency_provider, "bcv")
        self.assertEqual(self.company.currency_interval_unit, "manually")
        self.assertFalse(self.company.currency_next_execution_date)
        for code, value in (("usd", 1.0), ("ves", 871.3689), ("vef", 871.3689)):
            rate = self.env.ref(f"currency_rate_bcv_provider.demo_rate_{code}_20261005")
            self.assertEqual(rate.company_id, self.company)
            self.assertEqual(rate.currency_id.name, code.upper())
            self.assertTrue(rate.currency_id.active)
            self.assertEqual(rate.name, date(2026, 10, 5))
            self.assertAlmostEqual(rate.rate, value, places=8)

    def test_demo_rates_can_be_refreshed_manually(self):
        self.response.content = self.response.content.replace(
            b"871,36890000", b"901,36890000"
        )
        settings = self.env["res.config.settings"].create(
            {"company_id": self.company.id}
        )
        with patch(REQUEST_TARGET, return_value=self.response):
            settings.update_currency_rates_manually()

        rates = self.env["res.currency.rate"].search(
            [("company_id", "=", self.company.id), ("name", "=", date(2026, 10, 5))]
        )
        self.assertEqual(len(rates), 3)
        for code in ("ves", "vef"):
            rate = self.env.ref(f"currency_rate_bcv_provider.demo_rate_{code}_20261005")
            self.assertAlmostEqual(rate.rate, 901.3689, places=8)

    def test_demo_provider_can_use_the_native_scheduler(self):
        self.company.write(
            {
                "currency_interval_unit": "daily",
                "currency_next_execution_date": fields.Date.today(),
            }
        )
        with patch(REQUEST_TARGET, return_value=self.response) as request:
            self.env["res.company"].run_update_currency()
        request.assert_called_once()
        self.assertEqual(
            self.env.ref("currency_rate_bcv_provider.demo_rate_ves_20261005").rate,
            871.3689,
        )

    def test_demo_eur_company_updates_bolivars_without_changing_usd(self):
        self.company.currency_id = self.env.ref("base.EUR")
        settings = self.env["res.config.settings"].create(
            {"company_id": self.company.id}
        )
        with patch(REQUEST_TARGET, return_value=self.response):
            settings.update_currency_rates_manually()

        for code in ("ves", "vef"):
            rate = self.env.ref(f"currency_rate_bcv_provider.demo_rate_{code}_20261005")
            self.assertAlmostEqual(rate.rate, 981.17880877, places=8)
        self.assertEqual(
            self.env.ref("currency_rate_bcv_provider.demo_rate_usd_20261005").rate,
            1.0,
        )

    def test_demo_bolivar_company_updates_usd(self):
        self.company.currency_id = self.env.ref("base.VES")
        settings = self.env["res.config.settings"].create(
            {"company_id": self.company.id}
        )
        with patch(REQUEST_TARGET, return_value=self.response):
            settings.update_currency_rates_manually()

        usd_rate = self.env.ref("currency_rate_bcv_provider.demo_rate_usd_20261005")
        self.assertAlmostEqual(usd_rate.rate, 1.0 / 871.3689, places=12)
        self.assertAlmostEqual(
            usd_rate.with_company(self.company).inverse_company_rate,
            871.3689,
            places=8,
        )
        for code in ("ves", "vef"):
            rate = self.env.ref(f"currency_rate_bcv_provider.demo_rate_{code}_20261005")
            self.assertEqual(rate.rate, 1.0)
