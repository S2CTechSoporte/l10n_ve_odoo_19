from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRateConversion(DualCurrencyTestCommon):
    """The manual rate in the standard conversion functions and its orientation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eur = cls.env.ref("base.EUR")
        cls.gbp = cls.env.ref("base.GBP")
        (cls.eur | cls.gbp).active = True

    def _spec(self, rate=60.0, company=None, company_currency=None, reference=None):
        company = company or self.company
        return (
            company.root_id.id,
            (company_currency or self.ves).id,
            (reference or self.usd).id,
            rate,
        )

    def _rate(self, from_currency, to_currency, context=None, company=None):
        return self.env["res.currency"].with_context(
            **(context or {})
        )._get_conversion_rate(
            from_currency, to_currency, company or self.company, self.rate_date_invoice
        )

    def test_conversion_uses_manual_rate_in_both_directions(self):
        context = {"dual_currency_manual_rate": self._spec(60.0)}
        self.assertAlmostEqual(self._rate(self.ves, self.usd, context), 1 / 60.0)
        self.assertAlmostEqual(self._rate(self.usd, self.ves, context), 60.0)
        self.assertEqual(self._rate(self.usd, self.usd, context), 1)
        usd = self.usd.with_context(**context)
        ves = self.ves.with_context(**context)
        self.assertAlmostEqual(
            usd._convert(100.0, self.ves, self.company, self.rate_date_invoice), 6000.0
        )
        self.assertAlmostEqual(
            ves._convert(6000.0, self.usd, self.company, self.rate_date_invoice), 100.0
        )

    def test_conversion_keeps_system_rate_without_manual_rate(self):
        self.assertAlmostEqual(self._rate(self.usd, self.ves), 50.0)
        for context in (
            {},
            {"dual_currency_manual_rate": False},
            {"dual_currency_manual_rate": None},
        ):
            with self.subTest(context=context):
                self.assertAlmostEqual(self._rate(self.usd, self.ves, context), 50.0)
                self.assertAlmostEqual(
                    self.usd.with_context(**context)._convert(
                        100.0, self.ves, self.company, self.rate_date_invoice
                    ),
                    5000.0,
                )

    def test_conversion_ignores_the_foreign_manual_rate_context_key(self):
        for context in (
            {"manual_rate": 999.0},
            {"manual_rate": 999.0, "active_manutal_currency": True},
        ):
            with self.subTest(context=context):
                self.assertAlmostEqual(self._rate(self.usd, self.ves, context), 50.0)

    def test_conversion_only_replaces_the_company_reference_pair(self):
        self._set_rate(self.eur, self.company, self.rate_date_invoice, 0.5)
        context = {"dual_currency_manual_rate": self._spec(60.0)}
        for from_currency, to_currency in (
            (self.eur, self.ves),
            (self.ves, self.eur),
            (self.eur, self.usd),
            (self.usd, self.eur),
        ):
            with self.subTest(pair=f"{from_currency.name}/{to_currency.name}"):
                self.assertAlmostEqual(
                    self._rate(from_currency, to_currency, context),
                    self._rate(from_currency, to_currency),
                )

    def test_conversion_only_replaces_the_rates_of_the_document_company(self):
        other_company = self.env["res.company"].create(
            {
                "name": "Other Dual Currency Company",
                "currency_id": self.ves.id,
                "secondary_currency_id": self.usd.id,
            }
        )
        context = {"dual_currency_manual_rate": self._spec(60.0)}
        self.assertAlmostEqual(self._rate(self.ves, self.usd, context), 1 / 60.0)
        self.assertAlmostEqual(
            self._rate(self.ves, self.usd, context, company=other_company),
            self._rate(self.ves, self.usd, company=other_company),
        )

    def test_displayed_rate_is_stored_with_the_company_rate_orientation(self):
        # (company currency, reference currency, displayed rate, stored rate)
        cases = (
            (self.ves, self.usd, 880.0, 880.0),
            (self.usd, self.ves, 880.0, 1 / 880.0),
            (self.eur, self.usd, 0.8, 0.8),
            (self.usd, self.eur, 0.8, 1.25),
            (self.eur, self.gbp, 1.6, 1.6),
        )
        for company_currency, reference, displayed, stored in cases:
            with self.subTest(pair=f"{company_currency.name}/{reference.name}"):
                self.company.write(
                    {
                        "currency_id": company_currency.id,
                        "secondary_currency_id": reference.id,
                    }
                )
                self.assertAlmostEqual(
                    self.company._get_conversion_rate_from_display(displayed), stored
                )
                spec = self.company._get_manual_rate_spec(displayed)
                self.assertEqual(
                    spec[:3],
                    (self.company.root_id.id, company_currency.id, reference.id),
                )
                self.assertAlmostEqual(spec[3], stored)
                # The displayed rate is what the USD quotation indicator shows.
                shown = self.company._get_conversion_rate_display(stored)
                self.assertAlmostEqual(shown["conversion_rate_display"], displayed)

    def test_non_positive_manual_rates_are_rejected(self):
        for rate in (0, -1, -880.0):
            with self.subTest(rate=rate):
                with self.assertRaisesRegex(UserError, "must be strictly positive"):
                    self.company._get_conversion_rate_from_display(rate)
