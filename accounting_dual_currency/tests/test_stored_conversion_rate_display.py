from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import formatLang

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestStoredConversionRateDisplay(DualCurrencyTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eur = cls.env.ref("base.EUR")
        cls.gbp = cls.env.ref("base.GBP")
        (cls.eur | cls.gbp).active = True

    def _configure_pair(self, company_currency, reference_currency, stored_rate):
        self.company.write({
            "currency_id": company_currency.id,
            "secondary_currency_id": reference_currency.id if reference_currency else False,
        })
        for currency, rate in ((self.usd, 1), (self.eur, 1), (self.gbp, 2)):
            self._set_rate(currency, self.company, self.rate_date_invoice, rate)
        if reference_currency and reference_currency != company_currency:
            self._set_rate(reference_currency, self.company, self.rate_date_invoice, stored_rate)

    def _draft_records(self):
        moves = self.env["account.move"].create([
            {
                "move_type": "out_invoice", "company_id": self.company.id,
                "journal_id": self.sale_journal.id, "partner_id": self.partner_customer.id,
                "invoice_date": self.rate_date_invoice, "currency_id": self.company.currency_id.id,
            },
            {
                "move_type": "entry", "company_id": self.company.id,
                "journal_id": self.misc_journal.id, "date": self.rate_date_invoice,
                "currency_id": self.company.currency_id.id,
            },
        ])
        payment = self.env["account.payment"].create({
            "company_id": self.company.id, "journal_id": self.bank_journal.id,
            "partner_id": self.partner_customer.id, "payment_type": "inbound",
            "partner_type": "customer", "amount": 10, "date": self.rate_date_invoice,
            "currency_id": self.company.currency_id.id,
        })
        return (*moves, payment)

    def _assert_display(self, record, stored_rate, display_rate, currency, is_usd=True):
        self.assertAlmostEqual(record.conversion_rate, stored_rate)
        self.assertEqual(record.conversion_rate_display_currency_id, currency)
        self.assertEqual(record.conversion_rate_display_is_usd, is_usd)
        self.assertAlmostEqual(record.conversion_rate_display, currency.round(display_rate))
        self.assertAlmostEqual(record.conversion_rate, stored_rate)

    def _assert_invoice_payment_currencies(self, stored_rate):
        for move_type in ("out_invoice", "in_invoice"):
            for currency in (self.usd | self.eur | self.gbp):
                with self.subTest(move_type=move_type, currency=currency.name):
                    invoice = self._create_invoice(currency, 100, self.rate_date_invoice, move_type)
                    self._assert_display(invoice, stored_rate, 0.8, self.eur)
                    payment = self._create_payment(invoice, currency, 100, self.rate_date_invoice)
                    self._assert_display(payment, stored_rate, 0.8, self.eur)
                    self.assertTrue(invoice.company_currency_id.is_zero(invoice.amount_residual))

    def test_eur_company_preserves_stored_usd_rate_for_all_transaction_currencies(self):
        self._configure_pair(self.eur, self.usd, 0.8)
        self._assert_invoice_payment_currencies(0.8)

    def test_usd_company_inverts_stored_rate_for_all_transaction_currencies(self):
        self._configure_pair(self.usd, self.eur, 1.25)
        self._assert_invoice_payment_currencies(1.25)

    def test_non_usd_pair_keeps_reference_rate_and_company_symbol(self):
        self._configure_pair(self.eur, self.gbp, 1.6)
        for record in self._draft_records():
            self._assert_display(record, 1.6, 1.6, self.eur, is_usd=False)

    def test_missing_reference_keeps_existing_unit_rate(self):
        self._configure_pair(self.eur, False, 1)
        for record in self._draft_records():
            self._assert_display(record, 1, 1, self.eur, is_usd=False)

    def test_same_usd_currencies_keep_unit_quotation(self):
        self._configure_pair(self.usd, self.usd, 1)
        for record in self._draft_records():
            self._assert_display(record, 1, 1, self.usd)

    def test_display_only_reads_persisted_rate_without_dates_or_rate_lookups(self):
        self._configure_pair(self.usd, self.eur, 1.25)
        records = self._draft_records()
        self.env.flush_all()
        stored_rate = 1 / 0.78
        for record in records:
            record.write({"conversion_rate": stored_rate})
        self.env.flush_all()
        for record in records:
            record.invalidate_recordset([
                "conversion_rate_display", "conversion_rate_display_currency_id",
                "conversion_rate_display_is_usd",
            ])
        Currency = type(self.env["res.currency"])
        with (
            patch.object(fields.Date, "context_today", side_effect=AssertionError("Date lookup")),
            patch.object(Currency, "_get_conversion_rate", side_effect=AssertionError("Rate lookup")),
            patch.object(Currency, "_convert", side_effect=AssertionError("Currency conversion")),
        ):
            for record in records:
                self._assert_display(record, stored_rate, 0.78, self.eur)

    def test_display_follows_stored_rate_changes(self):
        self._configure_pair(self.usd, self.eur, 1.25)
        for record in self._draft_records():
            for stored_rate, display_rate in ((2, 0.5), (4, 0.25)):
                record.write({"conversion_rate": stored_rate})
                self._assert_display(record, stored_rate, display_rate, self.eur)

    def test_non_positive_stored_rate_cannot_be_inverted(self):
        self._configure_pair(self.usd, self.eur, 1.25)
        for rate in (0, -1):
            with self.subTest(rate=rate):
                with self.assertRaisesRegex(UserError, "stored conversion rate must be positive"):
                    self.company._get_conversion_rate_display(rate)

    def test_monetary_format_respects_language_and_counterpart_symbol_position(self):
        self._configure_pair(self.usd, self.eur, 1.25)
        lang = self.env["res.lang"]._activate_lang("es_ES")
        self.eur.write({"symbol": "\N{EURO SIGN}", "rounding": 0.01})
        for position in ("before", "after"):
            self.eur.position = position
            for record in self._draft_records():
                localized = record.with_context(lang=lang.code)
                formatted = formatLang(
                    localized.env, localized.conversion_rate_display,
                    currency_obj=localized.conversion_rate_display_currency_id,
                )
                expected = (
                    "0,80\N{NO-BREAK SPACE}\N{EURO SIGN}"
                    if position == "after"
                    else "\N{EURO SIGN}\N{NO-BREAK SPACE}0,80"
                )
                self.assertEqual(formatted, expected)

    def test_forms_show_readonly_monetary_rate_with_honest_labels(self):
        for model, view in (
            ("account.move", "account.view_move_form"),
            ("account.payment", "account.view_account_payment_form"),
        ):
            arch = etree.fromstring(
                self.env[model].get_view(view_id=self.env.ref(view).id, view_type="form")["arch"],
            )
            nodes = arch.xpath("//field[@name='conversion_rate_display']")
            self.assertEqual(len(nodes), 2)
            self.assertEqual(
                {node.get("invisible") for node in nodes},
                {"conversion_rate_display_is_usd", "not conversion_rate_display_is_usd"},
            )
            for node in nodes:
                self.assertEqual(node.get("widget"), "monetary")
                self.assertEqual(node.get("readonly"), "1")
                self.assertIn("conversion_rate_display_currency_id", node.get("options"))
            field = self.env[model]._fields["conversion_rate_display"]
            self.assertFalse(field.store)
            self.assertEqual(field.string, "USD Rate")
            self.assertEqual(field.currency_field, "conversion_rate_display_currency_id")
            self.assertEqual(len([node for node in nodes if node.get("string") == "Reference Rate"]), 1)

    def test_demo_stored_rate_display(self):
        company = self.env.ref(
            "accounting_dual_currency.demo_company_eur", raise_if_not_found=False,
        )
        if not company:
            self.skipTest("The database was initialized without demo data.")
        self.env.user.sudo().write({"company_ids": [Command.link(company.id)]})
        journal = self.env["account.journal"].with_company(company).create({
            "name": "Stored Rate Demo", "code": "USDD", "type": "general", "company_id": company.id,
        })
        move = self.env["account.move"].with_company(company).create({
            "move_type": "entry", "company_id": company.id, "journal_id": journal.id,
            "date": self.rate_date_invoice,
        })
        self._assert_display(move, 0.8, 0.8, self.eur)
