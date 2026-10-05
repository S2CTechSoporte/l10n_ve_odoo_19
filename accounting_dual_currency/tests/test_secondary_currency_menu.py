from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import formatLang


@tagged("post_install", "-at_install")
class TestSecondaryCurrencyMenu(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.eur = cls.env.ref("base.EUR")
        (cls.usd | cls.eur).active = True
        cls.company = cls.env["res.company"].create({
            "name": "Systray USD/EUR",
            "currency_id": cls.usd.id,
            "secondary_currency_id": cls.eur.id,
            "currency_provider": "ecb",
        })
        cls.other_company = cls.env["res.company"].create({
            "name": "Systray EUR/USD",
            "currency_id": cls.eur.id,
            "secondary_currency_id": cls.usd.id,
            "currency_provider": "ecb",
        })
        cls.today = fields.Date.today()
        cls.env["res.currency.rate"].create([
            {"currency_id": cls.usd.id, "company_id": cls.company.id,
             "name": cls.today, "rate": 1},
            {"currency_id": cls.eur.id, "company_id": cls.company.id,
             "name": cls.today, "rate": 1 / 1.12},
            {"currency_id": cls.eur.id, "company_id": cls.other_company.id,
             "name": cls.today, "rate": 1},
            {"currency_id": cls.usd.id, "company_id": cls.other_company.id,
             "name": cls.today, "rate": 1.25},
        ])
        cls.manager = new_test_user(
            cls.env, login="systray_manager", groups="account.group_account_manager",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )
        cls.employee = new_test_user(
            cls.env, login="systray_employee", groups="base.group_user",
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )

    def test_active_company_and_conversion_direction(self):
        company_model = self.env["res.company"].with_company(self.company)
        data = company_model.get_secondary_currency_systray()
        self.assertEqual(data["currency_name"], "EUR")
        self.assertAlmostEqual(data["amount"], 1.12)
        self.assertEqual(
            data["formatted_amount"],
            formatLang(company_model.env, 1.12, currency_obj=self.usd),
        )
        other_data = company_model.with_company(
            self.other_company
        ).get_secondary_currency_systray()
        self.assertEqual(other_data["currency_name"], "USD")
        self.assertAlmostEqual(other_data["amount"], 0.8)

    def test_absent_and_same_reference_currency(self):
        self.company.secondary_currency_id = False
        model = self.env["res.company"].with_company(self.company)
        self.assertFalse(model.get_secondary_currency_systray())
        self.company.secondary_currency_id = self.usd
        self.assertEqual(model.get_secondary_currency_systray()["amount"], 1)

    def test_read_only_employee_cannot_update(self):
        model = self.env["res.company"].with_user(
            self.employee
        ).with_company(self.company)
        self.assertFalse(model.get_secondary_currency_systray()["can_update"])
        with self.assertRaises(AccessError):
            model.update_secondary_currency_rates()

    def test_manager_calls_standard_updater_and_refreshes_rate(self):
        model = self.env["res.company"].with_user(
            self.manager
        ).with_company(self.company)
        self.assertTrue(model.get_secondary_currency_systray()["can_update"])
        Settings = type(self.env["res.config.settings"])
        standard_update = Settings.update_currency_rates_manually
        calls = []

        def record_standard_call(settings):
            calls.append(settings.company_id.id)
            return standard_update(settings)

        with (
            patch.object(Settings, "update_currency_rates_manually", record_standard_call),
            patch.object(type(model), "_parse_ecb_data", return_value={
                "USD": (1, self.today), "EUR": (1 / 1.2, self.today),
            }),
        ):
            data = model.update_secondary_currency_rates()
        self.assertEqual(calls, self.company.ids)
        self.assertAlmostEqual(data["amount"], 1.2)
        self.assertAlmostEqual(
            model.with_user(self.env.user).with_company(
                self.other_company
            ).get_secondary_currency_systray()["amount"], 0.8,
        )
        self.assertEqual(self.company.currency_interval_unit, "manually")

    def test_update_requires_provider_and_propagates_provider_errors(self):
        model = self.env["res.company"].with_user(
            self.manager
        ).with_company(self.company)
        self.company.currency_provider = False
        with self.assertRaises(UserError):
            model.update_secondary_currency_rates()
        self.company.currency_provider = "ecb"
        with patch.object(type(model), "_parse_ecb_data", side_effect=UserError("Provider unavailable")):
            with self.assertRaisesRegex(UserError, "Provider unavailable"):
                model.update_secondary_currency_rates()

    def test_disallowed_company_is_rejected_before_elevation(self):
        model = self.env["res.company"].with_user(self.manager).with_context(
            allowed_company_ids=self.other_company.ids,
        )
        with self.assertRaises(AccessError):
            model.update_secondary_currency_rates()

    def test_branch_uses_root_company_rates(self):
        branch = self.env["res.company"].create({
            "name": "Systray branch",
            "parent_id": self.company.id,
            "secondary_currency_id": self.eur.id,
        })
        model = self.env["res.company"].with_company(branch)
        self.assertAlmostEqual(model.get_secondary_currency_systray()["amount"], 1.12)
        with patch.object(type(model), "_parse_ecb_data", return_value={
            "USD": (1, self.today), "EUR": (1 / 1.3, self.today),
        }):
            self.assertAlmostEqual(model.update_secondary_currency_rates()["amount"], 1.3)

    def test_demo_reference_rate(self):
        company = self.env.ref(
            "accounting_dual_currency.demo_company_eur", raise_if_not_found=False,
        )
        if not company:
            self.skipTest("The database was initialized without demo data.")
        model = self.env["res.company"].with_company(company)
        with patch.object(fields.Date, "context_today", return_value=fields.Date.to_date("2026-01-10")):
            data = model.get_secondary_currency_systray()
        self.assertEqual(data["currency_name"], "USD")
        self.assertAlmostEqual(data["amount"], 0.8)
