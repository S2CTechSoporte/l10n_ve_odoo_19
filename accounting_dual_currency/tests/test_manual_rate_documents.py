from unittest.mock import patch

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, new_test_user, tagged

from .common import DualCurrencyTestCommon

MANUAL_RATE_GROUPS = "account.group_account_manager,base.group_system"


@tagged("post_install", "-at_install")
class TestManualRateDocuments(DualCurrencyTestCommon):
    """Invoices converted at the manual rate captured in the document."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.eur = cls.env.ref("base.EUR")
        cls.gbp = cls.env.ref("base.GBP")
        (cls.eur | cls.gbp).active = True

    def _create_draft_bill(self, currency, amount, **values):
        return self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "invoice_date": self.rate_date_invoice,
                "date": self.rate_date_invoice,
                "partner_id": self.partner_vendor.id,
                "journal_id": self.purchase_journal.id,
                "currency_id": currency.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "quantity": 1.0,
                            "price_unit": amount,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
                **values,
            }
        )

    def _bill_balances(self, bill):
        """Return the (payable debit, payable credit, expense debit, expense credit)."""
        payable = self._get_payment_term_line(bill)
        expense = bill.invoice_line_ids[:1]
        return payable.debit, payable.credit, expense.debit, expense.credit

    # ------------------------------------------------------------------ amounts

    def test_manual_rate_drives_the_native_debit_and_credit(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        payable = self._get_payment_term_line(bill)
        expense = bill.invoice_line_ids
        self.assertTrue(bill.manual_rate_active)
        self.assertAlmostEqual(bill.invoice_currency_rate, 1 / 60.0)
        self.assertAlmostEqual(bill.expected_currency_rate, 1 / 60.0)
        self.assertAlmostEqual(expense.debit, 6000.0)
        self.assertEqual(expense.credit, 0.0)
        self.assertAlmostEqual(payable.credit, 6000.0)
        self.assertEqual(payable.debit, 0.0)
        self.assertAlmostEqual(payable.balance, -6000.0)
        self.assertAlmostEqual(payable.amount_currency, -100.0)
        self.assertAlmostEqual(payable.currency_rate, 1 / 60.0)
        self.assertAlmostEqual(bill.amount_total_local_currency, 6000.0)
        self.assertAlmostEqual(bill.amount_total_secondary_currency, 100.0)
        self.assertAlmostEqual(bill.conversion_rate, 60.0)
        self.assertAlmostEqual(bill.conversion_rate_display, 60.0)
        self.assertEqual(bill.conversion_rate_display_currency_id, self.ves)
        self.assertTrue(bill.conversion_rate_display_is_usd)

    def test_disabled_manual_rate_keeps_the_system_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice"
        )
        self.assertFalse(bill.manual_rate)
        self.assertFalse(bill.manual_rate_active)
        self.assertEqual(bill.manual_conversion_rate, 0.0)
        self.assertAlmostEqual(bill.invoice_currency_rate, 1 / 50.0)
        _, payable_credit, expense_debit, _ = self._bill_balances(bill)
        self.assertAlmostEqual(payable_credit, 5000.0)
        self.assertAlmostEqual(expense_debit, 5000.0)
        self.assertAlmostEqual(bill.conversion_rate, 50.0)

    def test_draft_bill_follows_the_manual_rate_changes(self):
        bill = self._create_draft_bill(self.usd, 100.0)
        self.assertAlmostEqual(self._bill_balances(bill)[1], 5000.0)

        bill.write({"manual_rate": True, "manual_conversion_rate": 60.0})
        self.assertAlmostEqual(bill.invoice_currency_rate, 1 / 60.0)
        self.assertAlmostEqual(self._bill_balances(bill)[1], 6000.0)
        self.assertAlmostEqual(self._bill_balances(bill)[2], 6000.0)

        bill.manual_conversion_rate = 70.0
        self.assertAlmostEqual(self._bill_balances(bill)[1], 7000.0)
        self.assertAlmostEqual(bill.amount_total_local_currency, 7000.0)

        bill.manual_rate = False
        self.assertAlmostEqual(bill.invoice_currency_rate, 1 / 50.0)
        self.assertAlmostEqual(self._bill_balances(bill)[1], 5000.0)
        self.assertAlmostEqual(bill.amount_total_local_currency, 5000.0)

    def test_native_currency_rate_still_works_without_manual_rate(self):
        bill = self._create_draft_bill(self.usd, 100.0)
        bill.invoice_currency_rate = 1 / 55.0
        self.assertFalse(bill.manual_rate_active)
        self.assertAlmostEqual(self._bill_balances(bill)[1], 5500.0)

    def test_manual_rate_drives_the_reference_amounts_of_company_currency_bills(self):
        manual = self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        system = self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "in_invoice"
        )
        for bill, rate, reference in ((manual, 60.0, 100.0), (system, 50.0, 120.0)):
            with self.subTest(manual_rate=bill.manual_rate):
                payable = self._get_payment_term_line(bill)
                expense = bill.invoice_line_ids
                # The company currency amounts are not converted: they stay native.
                self.assertEqual(bill.invoice_currency_rate, 1.0)
                self.assertAlmostEqual(payable.credit, 6000.0)
                self.assertAlmostEqual(bill.amount_total_local_currency, 6000.0)
                self.assertAlmostEqual(bill.amount_total_secondary_currency, reference)
                self.assertAlmostEqual(bill.conversion_rate, rate)
                self.assertAlmostEqual(payable.conversion_rate, rate)
                self.assertAlmostEqual(payable.balance_secondary_currency, -reference)
                self.assertAlmostEqual(payable.credit_secondary_currency, reference)
                self.assertAlmostEqual(expense.debit_secondary_currency, reference)
                self.assertAlmostEqual(expense.price_unit_secondary_currency, reference)
                self.assertAlmostEqual(
                    expense.price_subtotal_secondary_currency, reference
                )

    def test_manual_rate_drives_the_reference_amounts_of_usd_bill_lines(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        payable = self._get_payment_term_line(bill)
        expense = bill.invoice_line_ids
        self.assertAlmostEqual(payable.conversion_rate, 60.0)
        self.assertAlmostEqual(payable.balance_secondary_currency, -100.0)
        self.assertAlmostEqual(expense.debit_secondary_currency, 100.0)
        self.assertAlmostEqual(expense.price_unit_secondary_currency, 100.0)
        self._assert_move_line_dual_fields(bill, manual_rate=60.0)

    # ------------------------------------------------------- rate orientation

    def _assert_orientation(
        self,
        company_currency,
        reference_currency,
        system_rates,
        document_currency,
        document_amount,
        displayed_rate,
        stored_rate,
        company_amount,
        document_rate,
        is_usd=True,
    ):
        self.company.write(
            {
                "currency_id": company_currency.id,
                "secondary_currency_id": reference_currency.id,
            }
        )
        for currency, inverse_rate in system_rates:
            self._set_rate(currency, self.company, self.rate_date_invoice, inverse_rate)
        system_bill = self._create_invoice(
            document_currency,
            document_amount,
            self.rate_date_invoice,
            "in_invoice",
        )
        bill = self._create_invoice(
            document_currency,
            document_amount,
            self.rate_date_invoice,
            "in_invoice",
            manual_rate=displayed_rate,
        )
        self.assertTrue(bill.manual_rate_active)
        self.assertEqual(bill.manual_rate_is_usd, is_usd)
        self.assertAlmostEqual(bill.manual_conversion_rate, displayed_rate)
        # The captured value is shown as typed whichever the company currency is.
        self.assertAlmostEqual(bill.conversion_rate, stored_rate)
        self.assertAlmostEqual(bill.conversion_rate_display, displayed_rate, places=2)
        self.assertEqual(bill.conversion_rate_display_is_usd, is_usd)
        self.assertEqual(
            bill.manual_rate_currency_id, bill.conversion_rate_display_currency_id
        )
        self.assertAlmostEqual(bill.invoice_currency_rate, document_rate)
        self.assertAlmostEqual(
            self._get_payment_term_line(bill).credit, company_amount, places=2
        )
        # Another bill of the same date keeps the system rate.
        self.assertNotAlmostEqual(
            self._get_payment_term_line(system_bill).credit, company_amount, places=2
        )
        self.assertFalse(system_bill.manual_rate_active)

        # The payments of the pair show the same rate and settle the bill.
        payment = self._create_payment(
            bill,
            document_currency,
            document_amount,
            self.rate_date_invoice,
            manual_rate=displayed_rate,
        )
        self.assertAlmostEqual(payment.conversion_rate, stored_rate)
        self.assertAlmostEqual(payment.conversion_rate_display, displayed_rate, places=2)
        self.assertAlmostEqual(payment.amount_local, company_amount, places=2)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertFalse(
            (bill.line_ids.matched_debit_ids | bill.line_ids.matched_credit_ids)
            .exchange_move_id
        )
        if document_currency != company_currency:
            other_bill = self._create_invoice(
                document_currency,
                document_amount,
                self.rate_date_invoice,
                "in_invoice",
                manual_rate=displayed_rate,
            )
            company_payment = self._create_payment(
                other_bill,
                company_currency,
                company_amount,
                self.rate_date_invoice,
                manual_rate=displayed_rate,
            )
            self.assertAlmostEqual(company_payment.amount_local, company_amount, places=2)
            self.assertIn(other_bill.payment_state, ("paid", "in_payment"))
            self.assertAlmostEqual(other_bill.amount_residual_secondary_currency, 0.0)

    def test_vendor_bill_in_usd_of_a_ves_company_shows_880_as_880(self):
        self._assert_orientation(
            self.ves,
            self.usd,
            [(self.usd, 50.0)],
            self.usd,
            100.0,
            displayed_rate=880.0,
            stored_rate=880.0,
            company_amount=88000.0,
            document_rate=1 / 880.0,
        )

    def test_vendor_bill_in_ves_of_a_usd_company_shows_880_as_880(self):
        self._assert_orientation(
            self.usd,
            self.ves,
            [(self.usd, 1.0), (self.ves, 1 / 850.0)],
            self.ves,
            88000.0,
            displayed_rate=880.0,
            stored_rate=1 / 880.0,
            company_amount=100.0,
            document_rate=880.0,
        )

    def test_vendor_bill_in_usd_of_an_eur_company_shows_the_dollar_in_euros(self):
        self._assert_orientation(
            self.eur,
            self.usd,
            [(self.eur, 1.0), (self.usd, 0.8)],
            self.usd,
            100.0,
            displayed_rate=0.9,
            stored_rate=0.9,
            company_amount=90.0,
            document_rate=1 / 0.9,
        )

    def test_vendor_bill_in_eur_of_a_usd_company_shows_the_dollar_in_euros(self):
        self._assert_orientation(
            self.usd,
            self.eur,
            [(self.usd, 1.0), (self.eur, 1.25)],
            self.eur,
            90.0,
            displayed_rate=0.9,
            stored_rate=1 / 0.9,
            company_amount=100.0,
            document_rate=0.9,
        )

    def test_vendor_bill_without_usd_in_the_pair_uses_the_reference_rate(self):
        self._assert_orientation(
            self.eur,
            self.gbp,
            [(self.eur, 1.0), (self.gbp, 1.5)],
            self.gbp,
            100.0,
            displayed_rate=1.6,
            stored_rate=1.6,
            company_amount=160.0,
            document_rate=1 / 1.6,
            is_usd=False,
        )

    # ------------------------------------------------------------ availability

    def test_manual_rate_is_only_available_for_the_company_and_reference_currencies(self):
        self._set_rate(self.gbp, self.company, self.rate_date_invoice, 40.0)
        for currency, available in (
            (self.ves, True),
            (self.usd, True),
            (self.gbp, False),
        ):
            with self.subTest(currency=currency.name):
                bill = self._create_draft_bill(currency, 100.0)
                self.assertEqual(bill.manual_rate_available, available)
                if available:
                    continue
                with self._assert_error(ValidationError, "manual rate is only available"):
                    bill.write({"manual_rate": True, "manual_conversion_rate": 40.0})
                with self._assert_error(ValidationError, "manual rate is only available"):
                    self._create_draft_bill(
                        currency, 100.0, manual_rate=True, manual_conversion_rate=40.0
                    )

    def test_manual_rate_is_not_available_without_a_different_reference_currency(self):
        for reference_currency in (False, self.ves):
            with self.subTest(reference=reference_currency and reference_currency.name):
                self.company.secondary_currency_id = reference_currency
                bill = self._create_draft_bill(self.ves, 100.0)
                self.assertFalse(bill.manual_rate_available)
                self.assertFalse(bill.manual_rate_active)
                with self._assert_error(ValidationError, "manual rate is only available"):
                    bill.write({"manual_rate": True, "manual_conversion_rate": 60.0})

    def test_manual_rate_must_be_positive(self):
        bill = self._create_draft_bill(self.usd, 100.0)
        for rate in (0.0, -60.0):
            with self.subTest(rate=rate):
                with self._assert_error(ValidationError, "strictly positive"):
                    bill.write({"manual_rate": True, "manual_conversion_rate": rate})
        bill.invalidate_recordset()
        self.assertFalse(bill.manual_rate)

    def test_manual_rate_of_a_posted_bill_cannot_be_modified(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        with self._assert_error(UserError, "cannot modify the manual rate"):
            bill.manual_conversion_rate = 70.0
        with self._assert_error(UserError, "cannot modify the manual rate"):
            bill.manual_rate = False
        # Writing the same values is not a modification.
        bill.write({"manual_rate": True, "manual_conversion_rate": 60.0})
        self.assertAlmostEqual(self._bill_balances(bill)[1], 6000.0)

        bill.button_draft()
        bill.manual_conversion_rate = 70.0
        self.assertAlmostEqual(self._bill_balances(bill)[1], 7000.0)
        bill.action_post()
        self.assertAlmostEqual(self._bill_balances(bill)[1], 7000.0)

    # ----------------------------------------------------------------- the form

    def test_form_defaults_the_manual_rate_to_the_system_rate(self):
        form = Form(
            self.env["account.move"].with_context(default_move_type="in_invoice")
        )
        form.partner_id = self.partner_vendor
        form.invoice_date = self.rate_date_invoice
        form.currency_id = self.usd
        self.assertFalse(form.manual_rate)
        form.manual_rate = True
        self.assertAlmostEqual(form.manual_conversion_rate, 50.0)
        form.manual_conversion_rate = 60.0
        self.assertAlmostEqual(form.invoice_currency_rate, 1 / 60.0)

    def test_form_resets_the_manual_rate_when_the_currency_is_not_available(self):
        self._set_rate(self.gbp, self.company, self.rate_date_invoice, 40.0)
        form = Form(
            self.env["account.move"].with_context(default_move_type="in_invoice")
        )
        form.partner_id = self.partner_vendor
        form.invoice_date = self.rate_date_invoice
        form.currency_id = self.usd
        form.manual_rate = True
        form.manual_conversion_rate = 60.0
        form.currency_id = self.gbp
        self.assertFalse(form.manual_rate)

    def test_manual_rate_is_not_copied_when_duplicating_a_bill(self):
        bill = self._create_draft_bill(
            self.usd, 100.0, manual_rate=True, manual_conversion_rate=60.0
        )
        duplicate = bill.copy()
        duplicate.invoice_date = self.rate_date_invoice
        self.assertFalse(duplicate.manual_rate)
        self.assertEqual(duplicate.manual_conversion_rate, 0.0)
        self.assertAlmostEqual(duplicate.invoice_currency_rate, 1 / 50.0)
        self.assertAlmostEqual(self._bill_balances(duplicate)[1], 5000.0)

    def test_display_of_a_manual_rate_only_reads_the_persisted_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=880.0
        )
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, manual_rate=880.0
        )
        self.env.flush_all()
        for record in (bill, payment):
            record.invalidate_recordset(
                [
                    "conversion_rate_display",
                    "conversion_rate_display_currency_id",
                    "conversion_rate_display_is_usd",
                ]
            )
        Currency = type(self.env["res.currency"])
        with (
            patch.object(fields.Date, "context_today", side_effect=AssertionError("Date lookup")),
            patch.object(Currency, "_get_conversion_rate", side_effect=AssertionError("Rate lookup")),
            patch.object(Currency, "_convert", side_effect=AssertionError("Currency conversion")),
        ):
            for record in (bill, payment):
                self.assertAlmostEqual(record.conversion_rate, 880.0)
                self.assertAlmostEqual(record.conversion_rate_display, 880.0)
                self.assertEqual(record.conversion_rate_display_currency_id, self.ves)
                self.assertTrue(record.conversion_rate_display_is_usd)

    def test_systray_quotation_ignores_the_manual_rate_of_documents(self):
        before = self.env["res.company"].get_secondary_currency_systray()
        self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=880.0
        )
        self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, manual_rate=880.0
        )
        after = self.env["res.company"].get_secondary_currency_systray()
        self.assertEqual(before, after)
        self.assertAlmostEqual(after["amount"], 54.0)

    def test_manual_rate_changes_are_tracked(self):
        for model in ("account.move", "account.payment"):
            with self.subTest(model=model):
                fields_ = self.env[model]._fields
                self.assertTrue(fields_["manual_rate"].tracking)
                self.assertTrue(fields_["manual_conversion_rate"].tracking)

    # ------------------------------------------------------------------- views

    def _view_arch(self, model, xmlid, user=None):
        record = self.env[model].with_user(user) if user else self.env[model]
        return etree.fromstring(
            record.get_view(view_id=self.env.ref(xmlid).id, view_type="form")["arch"]
        )

    def test_forms_show_the_manual_rate_to_accounting_managers(self):
        manager = new_test_user(
            self.env, login="adc_manual_manager", groups="account.group_account_manager"
        )
        for model, xmlid, extra_condition in (
            # The entry of a payment takes the rate of the payment.
            ("account.move", "account.view_move_form", " or origin_payment_id"),
            ("account.payment", "account.view_account_payment_form", ""),
            ("account.payment.register", "account.view_account_payment_register_form", ""),
        ):
            with self.subTest(model=model):
                arch = self._view_arch(model, xmlid, manager)
                (flag,) = arch.xpath("//field[@name='manual_rate']")
                self.assertEqual(
                    flag.get("invisible"),
                    f"not manual_rate_available{extra_condition}",
                )
                (value,) = arch.xpath("//field[@name='manual_conversion_rate']")
                self.assertEqual(value.get("digits"), "[12, 6]")
                self.assertEqual(value.get("required"), "manual_rate")
                self.assertEqual(
                    {
                        label.get("string")
                        for label in arch.xpath("//label[@for='manual_conversion_rate']")
                    },
                    {"Manual USD Rate", "Manual Reference Rate"},
                )
                for label in arch.xpath("//label[@for='manual_conversion_rate']"):
                    self.assertIn("manual_rate_is_usd", label.get("invisible"))
                # Customers and vendors share the controls: only availability decides.
                for node in (flag, value.getparent(), *arch.xpath("//label[@for='manual_conversion_rate']")):
                    self.assertNotIn("move_type", node.get("invisible"))
                    self.assertNotIn("partner_type", node.get("invisible"))
                if model != "account.payment.register":
                    self.assertEqual(flag.get("readonly"), "state != 'draft'")
                    self.assertEqual(value.get("readonly"), "state != 'draft'")
                    self.assertIn("state != 'draft'", value.getparent().get("invisible"))
                    for label in arch.xpath("//label[@for='manual_conversion_rate']"):
                        self.assertIn("state != 'draft'", label.get("invisible"))

    def test_forms_show_the_manual_rate_to_settings_administrators(self):
        # A settings administrator without the accounting manager group.
        administrator = new_test_user(
            self.env,
            login="adc_manual_settings",
            groups="base.group_system,account.group_account_invoice",
        )
        for model, xmlid in (
            ("account.move", "account.view_move_form"),
            ("account.payment", "account.view_account_payment_form"),
            ("account.payment.register", "account.view_account_payment_register_form"),
        ):
            with self.subTest(model=model):
                arch = self._view_arch(model, xmlid, administrator)
                self.assertTrue(arch.xpath("//field[@name='manual_rate']"))
                self.assertTrue(arch.xpath("//field[@name='manual_conversion_rate']"))
                self.assertTrue(arch.xpath("//label[@for='manual_conversion_rate']"))

    def test_forms_restrict_the_manual_rate_to_accounting_and_settings_administrators(self):
        for xmlid in (
            "accounting_dual_currency.account_move_form_dual_currency",
            "accounting_dual_currency.account_payment_form_dual_currency",
            "accounting_dual_currency.account_payment_register_form_dual_currency",
        ):
            with self.subTest(view=xmlid):
                arch = etree.fromstring(self.env.ref(xmlid).arch)
                for name in ("manual_rate", "manual_conversion_rate"):
                    (node,) = arch.xpath(f"//field[@name='{name}']")
                    self.assertEqual(
                        (node.get("groups") or node.getparent().get("groups")),
                        MANUAL_RATE_GROUPS,
                    )
                for label in arch.xpath("//label[@for='manual_conversion_rate']"):
                    self.assertEqual(label.get("groups"), MANUAL_RATE_GROUPS)

    def test_forms_hide_the_manual_rate_from_other_accounting_users(self):
        invoicing_user = new_test_user(
            self.env, login="adc_manual_invoicing", groups="account.group_account_invoice"
        )
        for model, xmlid in (
            ("account.move", "account.view_move_form"),
            ("account.payment", "account.view_account_payment_form"),
            ("account.payment.register", "account.view_account_payment_register_form"),
        ):
            with self.subTest(model=model):
                arch = self._view_arch(model, xmlid, invoicing_user)
                self.assertFalse(arch.xpath("//field[@name='manual_rate']"))
                self.assertFalse(arch.xpath("//field[@name='manual_conversion_rate']"))
                self.assertFalse(arch.xpath("//label[@for='manual_conversion_rate']"))
                self.assertTrue(arch.xpath("//field[@name='manual_rate_available']"))

    def test_native_currency_rate_is_readonly_while_the_manual_rate_is_in_use(self):
        arch = self._view_arch("account.move", "account.view_move_form")
        (rate_field,) = arch.xpath("//field[@name='invoice_currency_rate']")
        self.assertEqual(
            rate_field.get("readonly"), "state != 'draft' or manual_rate_active"
        )
        self.assertTrue(arch.xpath("//field[@name='manual_rate_active']"))

    def test_existing_rate_indicators_are_not_duplicated_by_the_manual_rate_fields(self):
        for model, xmlid in (
            ("account.move", "account.view_move_form"),
            ("account.payment", "account.view_account_payment_form"),
        ):
            with self.subTest(model=model):
                arch = self._view_arch(model, xmlid)
                self.assertEqual(
                    len(arch.xpath("//field[@name='conversion_rate_display']")), 2
                )
