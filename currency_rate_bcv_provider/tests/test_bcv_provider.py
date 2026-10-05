from datetime import date, timedelta
from unittest.mock import Mock, patch

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open
from odoo.tools.translate import PoFileReader


REQUEST_TARGET = "odoo.addons.currency_rate_bcv_provider.models.res_company.requests.get"
NATIVE_LOGGER = "odoo.addons.currency_rate_live.models.res_config_settings"
VALUE_DATE = date(2026, 10, 5)
BCV_RATE = 871.3689
BCV_QUOTATIONS = {
    "USD": BCV_RATE,
    "EUR": 981.17880877,
    "CNY": 129.97746121,
    "TRY": 17.73255527,
    "RUB": 10.39904073,
}


@tagged("post_install", "-at_install")
class TestBCVProvider(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.ves = cls.env.ref("base.VES")
        cls.vef = cls.env.ref("base.VEF")
        cls.eur = cls.env.ref("base.EUR")
        cls.currencies = cls.usd | cls.ves | cls.vef
        cls.foreign_currencies = {
            code: cls.env.ref(f"base.{code}") for code in BCV_QUOTATIONS
        }
        cls.supported_currencies = cls.currencies
        for currency in cls.foreign_currencies.values():
            cls.supported_currencies |= currency
        cls.supported_currencies.write({"active": True})
        cls.gbp = cls.env.ref("base.GBP")
        cls.gbp.active = True
        cls.company = cls.env["res.company"].create(
            {
                "name": "BCV Test Company",
                "country_id": cls.env.ref("base.ve").id,
                "currency_id": cls.usd.id,
                "currency_provider": "bcv",
                "currency_interval_unit": "manually",
            }
        )
        with file_open(
            "currency_rate_bcv_provider/tests/fixtures/bcv_rates.html", "rb"
        ) as fixture:
            cls.page = fixture.read()

    def setUp(self):
        super().setUp()
        self.response = Mock(content=self.page)
        self.response.raise_for_status.return_value = None

    def _company_rates(self, company=None):
        return self.env["res.currency.rate"].search(
            [("company_id", "=", (company or self.company).id)]
        )

    def test_provider_is_available_in_company_and_settings(self):
        for model in ("res.company", "res.config.settings"):
            selection = dict(
                self.env[model].fields_get(["currency_provider"])["currency_provider"][
                    "selection"
                ]
            )
            self.assertEqual(selection["bcv"], "[VE] Central Bank of Venezuela (BCV)")
            self.assertIn("ecb", selection)
        self.assertEqual(self.company.currency_provider, "bcv")

    def test_parser_returns_usd_based_rates_and_official_date(self):
        with patch(REQUEST_TARGET, return_value=self.response) as request:
            result = self.company._parse_bcv_data(self.currencies | self.eur)

        self.assertEqual(
            result,
            {
                "USD": (1.0, VALUE_DATE),
                "VES": (BCV_RATE, VALUE_DATE),
                "VEF": (BCV_RATE, VALUE_DATE),
            },
        )
        request.assert_called_once_with(
            "https://www.bcv.org.ve/", timeout=20, verify=False
        )
        self.response.raise_for_status.assert_called_once_with()

    def test_parser_supports_each_bolivar_code_independently(self):
        for currency in (self.ves, self.vef):
            with self.subTest(currency=currency.name):
                with patch(REQUEST_TARGET, return_value=self.response):
                    result = self.company._parse_bcv_data(self.usd | currency)
                self.assertEqual(
                    result,
                    {"USD": (1.0, VALUE_DATE), currency.name: (BCV_RATE, VALUE_DATE)},
                )

    def test_parser_includes_foreign_company_bases_with_usd_cross_rates(self):
        companies = self.env["res.company"].create(
            [
                {
                    "name": f"BCV Parser {code}",
                    "currency_id": currency.id,
                    "currency_provider": "bcv",
                }
                for code, currency in self.foreign_currencies.items()
            ]
        )
        with patch(REQUEST_TARGET, return_value=self.response) as request:
            result = companies._parse_bcv_data(self.supported_currencies)

        request.assert_called_once()
        self.assertEqual(set(result), set(BCV_QUOTATIONS) | {"VES", "VEF"})
        self.assertEqual(result["VES"], (BCV_RATE, VALUE_DATE))
        self.assertEqual(result["VEF"], (BCV_RATE, VALUE_DATE))
        for code, quotation in BCV_QUOTATIONS.items():
            self.assertAlmostEqual(result[code][0], BCV_RATE / quotation, places=12)
            self.assertEqual(result[code][1], VALUE_DATE)

    def test_parser_requires_usd_and_a_bolivar_currency(self):
        for currencies in (self.usd, self.ves | self.vef, self.eur):
            with self.subTest(currencies=currencies.mapped("name")):
                with patch(REQUEST_TARGET) as request:
                    with self.assertRaisesRegex(UserError, "requires USD"):
                        self.company._parse_bcv_data(currencies)
                request.assert_not_called()

    def test_extractor_supports_spanish_thousands_and_outer_whitespace(self):
        page = self.page.replace(b"871,36890000", b" \xc2\xa01.871,36890000 \n")
        rate, value_date = self.company._extract_bcv_rate(page)
        self.assertAlmostEqual(rate, 1871.3689, places=8)
        self.assertEqual(value_date, VALUE_DATE)

    def test_extractor_rejects_malformed_or_nonpositive_quotations(self):
        for value in (
            b"0,00000000",
            b"-1,00000000",
            b"NaN",
            b"871.36890000",
            b"12.34,5600",
            b"8 71,36890000",
            b"9" * 400 + b",00000000",
        ):
            with self.subTest(value=value[:30]):
                with self.assertRaises(UserError):
                    self.company._extract_bcv_rate(
                        self.page.replace(b"871,36890000", value)
                    )

    def test_extractor_rejects_missing_or_ambiguous_blocks(self):
        invalid_pages = (
            b"",
            self.page.replace(b'id="dolar"', b'id="not-dolar"'),
            self.page.replace(
                b'<strong class="strong-tb">871,36890000</strong>',
                b"<span>871,36890000</span>",
            ),
            self.page.replace(
                b'<strong class="strong-tb">871,36890000</strong>',
                b"<strong>871,36890000</strong><strong>1,00</strong>",
            ),
            self.page + b'<div id="dolar"><strong>1,00</strong></div>',
        )
        for page in invalid_pages:
            with self.subTest(page=page[:60]):
                with self.assertRaises(UserError):
                    self.company._extract_bcv_rate(page)

    def test_extractor_rejects_missing_ambiguous_or_invalid_value_date(self):
        invalid_pages = (
            self.page.replace(b'class="date-display-single"', b'class="no-date"'),
            self.page.replace(b"2026-10-05T00:00:00-04:00", b"not-a-date"),
            self.page.replace(b"2026-10-05T00:00:00-04:00", b"2026-02-30T00:00:00-04:00"),
            self.page.replace(
                b"Fecha Valor:",
                b'Fecha Valor: <span class="date-display-single" '
                b'content="2026-10-06T00:00:00-04:00">Duplicate date</span>',
            ),
        )
        for page in invalid_pages:
            with self.subTest(page=page[:60]):
                with self.assertRaises(UserError):
                    self.company._extract_bcv_rate(page)

    def test_extractor_keeps_the_published_calendar_date(self):
        page = self.page.replace(
            b"2026-10-05T00:00:00-04:00", b"2026-10-06T23:00:00-04:00"
        )
        self.assertEqual(
            self.company._extract_bcv_rate(page), (BCV_RATE, date(2026, 10, 6))
        )

    def test_extractor_supports_each_published_currency(self):
        for code, quotation in BCV_QUOTATIONS.items():
            with self.subTest(currency=code):
                self.assertEqual(
                    self.company._extract_bcv_rate(self.page, currency_code=code),
                    (quotation, VALUE_DATE),
                )

    def test_extractor_rejects_unpublished_currency(self):
        with self.assertRaisesRegex(UserError, "GBP"):
            self.company._extract_bcv_rate(self.page, currency_code="GBP")

    def test_manual_update_uses_usd_company_rate_convention(self):
        settings = self.env["res.config.settings"].create(
            {"company_id": self.company.id}
        )
        with patch(REQUEST_TARGET, return_value=self.response):
            settings.update_currency_rates_manually()

        rates = self._company_rates()
        self.assertEqual(len(rates), 3)
        self.assertEqual(set(rates.mapped("name")), {VALUE_DATE})
        self.assertEqual(
            rates.filtered(lambda rate: rate.currency_id == self.usd).rate, 1.0
        )
        for currency in (self.ves, self.vef):
            rate = rates.filtered(lambda item: item.currency_id == currency)
            self.assertAlmostEqual(rate.rate, BCV_RATE, places=8)
            self.assertAlmostEqual(
                self.usd._convert(
                    1.0, currency, self.company, VALUE_DATE, round=False
                ),
                BCV_RATE,
                places=8,
            )

    def test_bolivar_company_rates_are_normalized_and_convert_correctly(self):
        for currency in (self.ves, self.vef):
            with self.subTest(currency=currency.name):
                company = self.env["res.company"].create(
                    {
                        "name": f"BCV {currency.name} Company",
                        "currency_id": currency.id,
                        "currency_provider": "bcv",
                    }
                )
                with patch(REQUEST_TARGET, return_value=self.response):
                    self.assertTrue(company.update_currency_rates())

                rates = self._company_rates(company)
                usd_rate = rates.filtered(lambda rate: rate.currency_id == self.usd)
                self.assertAlmostEqual(usd_rate.rate, 1.0 / BCV_RATE, places=12)
                self.assertAlmostEqual(
                    usd_rate.with_company(company).inverse_company_rate,
                    BCV_RATE,
                    places=8,
                )
                for bolivar in (self.ves, self.vef):
                    self.assertEqual(
                        rates.filtered(lambda rate: rate.currency_id == bolivar).rate,
                        1.0,
                    )
                self.assertAlmostEqual(
                    self.usd._convert(1.0, currency, company, VALUE_DATE, round=False),
                    BCV_RATE,
                    places=8,
                )

    def test_foreign_company_manual_update_targets_bolivars_only(self):
        for code, currency in self.foreign_currencies.items():
            with self.subTest(company_currency=code):
                company = self.env["res.company"].create(
                    {
                        "name": f"BCV Manual {code}",
                        "currency_id": currency.id,
                        "currency_provider": "bcv",
                    }
                )
                unrelated_rates = self.env["res.currency.rate"].create(
                    [
                        {
                            "currency_id": other_currency.id,
                            "company_id": company.id,
                            "name": VALUE_DATE,
                            "rate": 7.25,
                        }
                        for other_code, other_currency in self.foreign_currencies.items()
                        if other_code != code
                    ]
                )
                settings = self.env["res.config.settings"].create(
                    {"company_id": company.id}
                )
                with patch(REQUEST_TARGET, return_value=self.response):
                    settings.update_currency_rates_manually()

                rates = self._company_rates(company)
                updated_rates = rates - unrelated_rates
                self.assertEqual(
                    set(updated_rates.mapped("currency_id.name")), {code, "VES", "VEF"}
                )
                self.assertTrue(all(rate.rate == 7.25 for rate in unrelated_rates))
                self.assertEqual(
                    updated_rates.filtered(lambda rate: rate.currency_id == currency).rate,
                    1.0,
                )
                for bolivar in (self.ves, self.vef):
                    self.assertAlmostEqual(
                        updated_rates.filtered(
                            lambda rate: rate.currency_id == bolivar
                        ).rate,
                        BCV_QUOTATIONS[code],
                        places=8,
                    )
                    self.assertAlmostEqual(
                        currency._convert(
                            1.0, bolivar, company, VALUE_DATE, round=False
                        ),
                        BCV_QUOTATIONS[code],
                        places=8,
                    )

    def test_bolivar_company_manual_update_targets_usd_only(self):
        for bolivar in (self.ves, self.vef):
            with self.subTest(company_currency=bolivar.name):
                company = self.env["res.company"].create(
                    {
                        "name": f"BCV Manual {bolivar.name}",
                        "currency_id": bolivar.id,
                        "currency_provider": "bcv",
                    }
                )
                unrelated_rates = self.env["res.currency.rate"].create(
                    [
                        {
                            "currency_id": currency.id,
                            "company_id": company.id,
                            "name": VALUE_DATE,
                            "rate": 7.25,
                        }
                        for code, currency in self.foreign_currencies.items()
                        if code != "USD"
                    ]
                )
                settings = self.env["res.config.settings"].create(
                    {"company_id": company.id}
                )
                with patch(REQUEST_TARGET, return_value=self.response):
                    settings.update_currency_rates_manually()

                updated_rates = self._company_rates(company) - unrelated_rates
                self.assertEqual(
                    set(updated_rates.mapped("currency_id.name")), {"USD", "VES", "VEF"}
                )
                self.assertTrue(all(rate.rate == 7.25 for rate in unrelated_rates))
                usd_rate = updated_rates.filtered(lambda rate: rate.currency_id == self.usd)
                self.assertAlmostEqual(usd_rate.rate, 1.0 / BCV_RATE, places=12)
                self.assertAlmostEqual(
                    usd_rate.with_company(company).inverse_company_rate,
                    BCV_RATE,
                    places=8,
                )

    def test_repeated_update_reuses_rates_for_the_official_date(self):
        with patch(REQUEST_TARGET, return_value=self.response):
            self.company.update_currency_rates()
            rate_ids = self._company_rates().ids
            self.response.content = self.page.replace(b"871,36890000", b"901,36890000")
            self.company.update_currency_rates()

        rates = self._company_rates()
        self.assertEqual(rates.ids, rate_ids)
        self.assertEqual(len(rates), 3)
        self.assertAlmostEqual(
            rates.filtered(lambda rate: rate.currency_id == self.ves).rate,
            901.3689,
            places=8,
        )
        self.assertAlmostEqual(
            rates.filtered(lambda rate: rate.currency_id == self.vef).rate,
            901.3689,
            places=8,
        )

    def test_update_does_not_activate_or_write_inactive_vef(self):
        self.vef.active = False
        with patch(REQUEST_TARGET, return_value=self.response):
            self.company.update_currency_rates()

        self.assertFalse(self.vef.active)
        self.assertEqual(
            set(self._company_rates().mapped("currency_id.name")), {"USD", "VES"}
        )

    def test_update_supports_legacy_vef_without_active_ves(self):
        self.ves.active = False
        with patch(REQUEST_TARGET, return_value=self.response):
            self.company.update_currency_rates()

        self.assertFalse(self.ves.active)
        rates = self._company_rates()
        self.assertEqual(set(rates.mapped("currency_id.name")), {"USD", "VEF"})
        self.assertAlmostEqual(
            rates.filtered(lambda rate: rate.currency_id == self.vef).rate,
            BCV_RATE,
            places=8,
        )

    def test_unsupported_company_currency_is_rejected(self):
        self.company.currency_id = self.gbp
        with patch(REQUEST_TARGET, return_value=self.response):
            with self.assertRaisesRegex(UserError, "GBP"):
                self.company.update_currency_rates()
        self.assertFalse(self._company_rates())

    def test_parser_requires_the_company_currency_in_available_currencies(self):
        self.company.currency_id = self.eur
        with patch(REQUEST_TARGET) as request:
            with self.assertRaisesRegex(UserError, "active.*EUR"):
                self.company._parse_bcv_data(self.currencies)
        request.assert_not_called()

    def test_missing_or_invalid_foreign_quotation_leaves_all_companies_unchanged(self):
        company = self.env["res.company"].create(
            {
                "name": "BCV Invalid EUR Company",
                "currency_id": self.eur.id,
                "currency_provider": "bcv",
            }
        )
        invalid_pages = (
            self.page.replace(b'id="euro"', b'id="no-euro"'),
            self.page.replace(b"981,17880877", b"0,00000000"),
            self.page.replace(b"981,17880877", b"NaN"),
            self.page + b'<div id="euro"><strong>1,00</strong></div>',
        )
        for page in invalid_pages:
            with self.subTest(page=page[:60]):
                self.response.content = page
                with patch(REQUEST_TARGET, return_value=self.response):
                    with self.assertRaisesRegex(UserError, "EUR"):
                        (self.company | company).update_currency_rates()
                self.assertFalse(self._company_rates())
                self.assertFalse(self._company_rates(company))

    def test_foreign_quotation_must_share_the_usd_value_date(self):
        self.company.currency_id = self.eur
        self.response.content = self.page.replace(b'id="euro"', b'id="no-euro"') + (
            b'<div class="views-row"><div id="euro"><strong>981,17880877</strong></div>'
            b'<span class="date-display-single" content="2026-10-06T00:00:00-04:00">'
            b"Other value date</span></div>"
        )
        with patch(REQUEST_TARGET, return_value=self.response):
            with self.assertRaisesRegex(UserError, "same official value date"):
                self.company.update_currency_rates()
        self.assertFalse(self._company_rates())

    def test_nonfinite_foreign_cross_rate_is_rejected(self):
        self.company.currency_id = self.eur
        self.response.content = self.page.replace(
            b"981,17880877", b"0," + b"0" * 307 + b"1"
        )
        with patch(REQUEST_TARGET, return_value=self.response):
            with self.assertRaisesRegex(UserError, "EUR"):
                self.company.update_currency_rates()
        self.assertFalse(self._company_rates())

    def test_network_and_http_failures_leave_rates_unchanged(self):
        settings = self.env["res.config.settings"].create(
            {"company_id": self.company.id}
        )
        errors = (
            requests.Timeout("Timed out"),
            requests.ConnectionError("Connection refused"),
            requests.exceptions.SSLError("TLS handshake failed"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch(REQUEST_TARGET, side_effect=error):
                    with self.assertRaises(UserError):
                        settings.update_currency_rates_manually()
                self.assertFalse(self._company_rates())

        self.response.raise_for_status.side_effect = requests.HTTPError("HTTP 503")
        with patch(REQUEST_TARGET, return_value=self.response):
            with self.assertRaisesRegex(UserError, "HTTP 503"):
                settings.update_currency_rates_manually()
        self.assertFalse(self._company_rates())

    def test_invalid_page_leaves_existing_rates_unchanged(self):
        with patch(REQUEST_TARGET, return_value=self.response):
            self.company.update_currency_rates()
            original_rates = {rate.id: rate.rate for rate in self._company_rates()}
            self.response.content = self.page.replace(b"871,36890000", b"0,00000000")
            with self.assertRaises(UserError):
                self.company.update_currency_rates()

        self.assertEqual(
            {rate.id: rate.rate for rate in self._company_rates()}, original_rates
        )

    def test_scheduler_uses_the_native_provider_and_advances_the_schedule(self):
        today = fields.Date.today()
        self.company.write(
            {"currency_interval_unit": "daily", "currency_next_execution_date": today}
        )
        future_company = self.env["res.company"].create(
            {
                "name": "BCV Future Company",
                "currency_id": self.usd.id,
                "currency_provider": "bcv",
                "currency_interval_unit": "daily",
                "currency_next_execution_date": today + timedelta(days=1),
            }
        )
        with patch(REQUEST_TARGET, return_value=self.response) as request:
            self.env["res.company"].run_update_currency()

        request.assert_called_once()
        self.assertEqual(
            self.company.currency_next_execution_date, today + timedelta(days=1)
        )
        self.assertEqual(len(self._company_rates()), 3)
        self.assertFalse(self._company_rates(future_company))

    def test_scheduled_failure_is_logged_without_creating_rates(self):
        today = fields.Date.today()
        self.company.write(
            {"currency_interval_unit": "daily", "currency_next_execution_date": today}
        )
        with patch(REQUEST_TARGET, side_effect=requests.Timeout("Timed out")):
            with self.assertLogs(NATIVE_LOGGER, level="WARNING") as logs:
                self.env["res.company"].run_update_currency()

        self.assertIn(
            "Could not retrieve the official BCV exchange rate", " ".join(logs.output)
        )
        self.assertFalse(self._company_rates())
        self.assertEqual(
            self.company.currency_next_execution_date, today + timedelta(days=1)
        )

    def test_scheduler_normalizes_all_supported_company_currencies(self):
        today = fields.Date.today()
        companies = self.env["res.company"].create(
            [
                {
                    "name": f"BCV Scheduled {currency.name}",
                    "currency_id": currency.id,
                    "currency_provider": "bcv",
                    "currency_interval_unit": "daily",
                    "currency_next_execution_date": today,
                }
                for currency in self.supported_currencies
            ]
        )
        with patch(REQUEST_TARGET, return_value=self.response) as request:
            self.env["res.company"].run_update_currency()

        request.assert_called_once()
        for company in companies:
            code = company.currency_id.name
            with self.subTest(company_currency=code):
                rates = self._company_rates(company)
                expected_codes = {"VES", "VEF", code}
                if code in {"VES", "VEF"}:
                    expected_codes.add("USD")
                    quotation = BCV_RATE
                    source_currency = self.usd
                    target_currency = company.currency_id
                else:
                    quotation = BCV_QUOTATIONS[code]
                    source_currency = company.currency_id
                    target_currency = self.ves
                self.assertEqual(set(rates.mapped("currency_id.name")), expected_codes)
                self.assertEqual(set(rates.mapped("name")), {VALUE_DATE})
                self.assertEqual(
                    company.currency_next_execution_date, today + timedelta(days=1)
                )
                self.assertEqual(
                    rates.filtered(
                        lambda rate: rate.currency_id == company.currency_id
                    ).rate,
                    1.0,
                )
                self.assertAlmostEqual(
                    source_currency._convert(
                        1.0, target_currency, company, VALUE_DATE, round=False
                    ),
                    quotation,
                    places=8,
                )

    def test_multiple_companies_share_one_fetch_and_keep_separate_rates(self):
        company = self.env["res.company"].create(
            {
                "name": "BCV VES Group Company",
                "currency_id": self.ves.id,
                "currency_provider": "bcv",
            }
        )
        with patch(REQUEST_TARGET, return_value=self.response) as request:
            self.assertTrue((self.company | company).update_currency_rates())

        request.assert_called_once()
        self.assertEqual(len(self._company_rates()), 3)
        self.assertEqual(len(self._company_rates(company)), 3)
        self.assertAlmostEqual(
            self._company_rates().filtered(lambda rate: rate.currency_id == self.ves).rate,
            BCV_RATE,
            places=8,
        )
        self.assertEqual(
            self._company_rates(company).filtered(
                lambda rate: rate.currency_id == self.ves
            ).rate,
            1.0,
        )

    def test_other_providers_keep_their_native_behavior(self):
        self.company.currency_provider = "ecb"
        with patch.object(
            type(self.company),
            "_parse_ecb_data",
            return_value={"USD": (1.0, VALUE_DATE), "EUR": (0.9, VALUE_DATE)},
        ) as ecb_parser:
            with patch(REQUEST_TARGET) as bcv_request:
                self.assertTrue(self.company.update_currency_rates())

        ecb_parser.assert_called_once()
        bcv_request.assert_not_called()
        self.assertEqual(
            set(self._company_rates().mapped("currency_id.name")), {"USD", "EUR"}
        )
        self.assertEqual(
            self._company_rates().filtered(lambda rate: rate.currency_id == self.eur).rate,
            0.9,
        )

    def test_translation_file_uses_valid_odoo_references(self):
        with file_open("currency_rate_bcv_provider/i18n/es_419.po", "rb") as po_file:
            rows = list(PoFileReader(po_file))
        self.assertTrue(rows)
        self.assertEqual(
            {row["module"] for row in rows}, {"currency_rate_bcv_provider"}
        )
        self.assertTrue(all(row["type"] in {"code", "model"} for row in rows))
        self.assertTrue(all(row["src"] and row["value"] for row in rows))

    def test_venezuelan_spanish_uses_the_latin_american_translation(self):
        self.env["res.lang"]._activate_lang("es_VE")
        module = self.env["ir.module.module"].search(
            [("name", "=", "currency_rate_bcv_provider")]
        )
        module._update_translations(["es_VE"], overwrite=True)

        for model in ("res.company", "res.config.settings"):
            field = self.env[model].with_context(lang="es_VE").fields_get(
                ["currency_provider"]
            )["currency_provider"]
            self.assertEqual(
                dict(field["selection"])["bcv"], "[VE] Banco Central de Venezuela (BCV)"
            )

        with self.assertRaises(UserError) as error:
            self.company.with_context(lang="es_VE")._parse_bcv_data(self.usd)
        self.assertEqual(
            str(error.exception),
            "El proveedor BCV requiere que USD y al menos una de las monedas "
            "VES o VEF estén activas.",
        )
        with self.assertRaises(UserError) as error:
            self.company.with_context(lang="es_VE")._extract_bcv_rate(
                self.page.replace(b"981,17880877", b"0,00000000"),
                currency_code="EUR",
            )
        self.assertEqual(
            str(error.exception),
            "La cotización de EUR del BCV debe ser finita y estrictamente positiva.",
        )
