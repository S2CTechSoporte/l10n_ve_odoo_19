from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import DualCurrencyTestCommon

ACCESS_ERROR = "set or change the manual rate"


@tagged("post_install", "-at_install")
class TestManualRateAccess(DualCurrencyTestCommon):
    """Only accounting and settings administrators capture or change a manual rate.

    The groups are checked by the server, not only by the views, while a document can
    still carry the rate of its source document.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.invoicing_user = cls._new_user(
            "adc_access_invoicing", "account.group_account_invoice"
        )
        cls.manager_user = cls._new_user(
            "adc_access_manager", "account.group_account_manager"
        )
        cls.settings_user = cls._new_user(
            "adc_access_settings", "account.group_account_invoice,base.group_system"
        )

    @classmethod
    def _new_user(cls, login, groups):
        return new_test_user(
            cls.env,
            login=login,
            groups=groups,
            company_id=cls.company.id,
            company_ids=[Command.set(cls.company.ids)],
        )

    def _invoice_values(self, move_type="out_invoice", **values):
        is_customer = move_type.startswith("out_")
        return {
            "move_type": move_type,
            "invoice_date": self.rate_date_invoice,
            "date": self.rate_date_invoice,
            "partner_id": (self.partner_customer if is_customer else self.partner_vendor).id,
            "journal_id": (self.sale_journal if is_customer else self.purchase_journal).id,
            "currency_id": self.usd.id,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "name": self.product.name,
                        "quantity": 1.0,
                        "price_unit": 100.0,
                        "tax_ids": [Command.clear()],
                    }
                )
            ],
            **values,
        }

    def _payment_values(self, payment_type="inbound", **values):
        is_customer = payment_type == "inbound"
        return {
            "payment_type": payment_type,
            "partner_type": "customer" if is_customer else "supplier",
            "partner_id": (self.partner_customer if is_customer else self.partner_vendor).id,
            "amount": 100.0,
            "date": self.rate_date_invoice,
            "currency_id": self.usd.id,
            "journal_id": self.bank_journal.id,
            **values,
        }

    def _wizard_values(self, **values):
        return {
            "payment_date": self.rate_date_invoice,
            "journal_id": self.bank_journal.id,
            **values,
        }

    def _wizard(self, user, invoice, **values):
        return self.env["account.payment.register"].with_user(user).with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create(self._wizard_values(**values))

    def _reverse(self, user, invoice):
        wizard = self.env["account.move.reversal"].with_user(user).with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create(
            {
                "move_ids": [Command.set(invoice.ids)],
                "company_id": self.company.id,
                "journal_id": invoice.journal_id.id,
                "date": self.rate_date_third,
                "reason": "Manual rate access test",
            }
        )
        wizard.refund_moves()
        return wizard.new_move_ids

    # --------------------------------------------------------------- creation

    def test_invoicing_user_cannot_create_documents_with_a_manual_rate(self):
        manual = {"manual_rate": True, "manual_conversion_rate": 60.0}
        entry_values = {
            "move_type": "entry",
            "journal_id": self.misc_journal.id,
            "date": self.rate_date_invoice,
            **manual,
        }
        for model, values in (
            ("account.move", self._invoice_values("out_invoice", **manual)),
            ("account.move", self._invoice_values("in_invoice", **manual)),
            ("account.move", entry_values),
            ("account.payment", self._payment_values("inbound", **manual)),
            ("account.payment", self._payment_values("outbound", **manual)),
        ):
            with self.subTest(model=model), self._assert_error(AccessError, ACCESS_ERROR):
                self.env[model].with_user(self.invoicing_user).create(values)

    def test_invoicing_user_creates_documents_without_a_manual_rate(self):
        invoice = self.env["account.move"].with_user(self.invoicing_user).create(
            self._invoice_values(manual_rate=False, manual_conversion_rate=0.0)
        )
        payment = self.env["account.payment"].with_user(self.invoicing_user).create(
            self._payment_values()
        )
        self.assertFalse(invoice.manual_rate)
        self.assertFalse(payment.manual_rate)

    def test_accounting_and_settings_administrators_can_create_documents_with_a_manual_rate(self):
        manual = {"manual_rate": True, "manual_conversion_rate": 60.0}
        for user in (self.manager_user, self.settings_user):
            with self.subTest(user=user.login):
                invoice = self.env["account.move"].with_user(user).create(
                    self._invoice_values(**manual)
                )
                payment = self.env["account.payment"].with_user(user).create(
                    self._payment_values(**manual)
                )
                self.assertTrue(invoice.manual_rate_active)
                self.assertTrue(payment.manual_rate_active)

    def test_sudo_and_the_superuser_are_not_restricted(self):
        manual = {"manual_rate": True, "manual_conversion_rate": 60.0}
        invoice = self.env["account.move"].with_user(self.invoicing_user).sudo().create(
            self._invoice_values(**manual)
        )
        self.assertTrue(invoice.manual_rate_active)

    # ---------------------------------------------------------------- changes

    def test_invoicing_user_cannot_change_the_manual_rate_of_a_draft_document(self):
        manual_invoice = self.env["account.move"].create(
            self._invoice_values(manual_rate=True, manual_conversion_rate=60.0)
        )
        system_invoice = self.env["account.move"].create(self._invoice_values())
        manual_payment = self.env["account.payment"].create(
            self._payment_values(manual_rate=True, manual_conversion_rate=60.0)
        )
        for record, values in (
            (manual_invoice, {"manual_conversion_rate": 70.0}),
            (manual_invoice, {"manual_rate": False}),
            (system_invoice, {"manual_rate": True, "manual_conversion_rate": 60.0}),
            (manual_payment, {"manual_conversion_rate": 70.0}),
            (manual_payment, {"manual_rate": False}),
        ):
            with self.subTest(record=record._name, values=values):
                with self._assert_error(AccessError, ACCESS_ERROR):
                    record.with_user(self.invoicing_user).write(values)
        self.assertAlmostEqual(manual_invoice.manual_conversion_rate, 60.0)
        self.assertTrue(manual_invoice.manual_rate)
        self.assertFalse(system_invoice.manual_rate)
        self.assertAlmostEqual(manual_payment.manual_conversion_rate, 60.0)

    def test_writing_the_current_manual_rate_is_not_a_change(self):
        invoice = self.env["account.move"].create(
            self._invoice_values(manual_rate=True, manual_conversion_rate=60.0)
        )
        invoice.with_user(self.invoicing_user).write(
            {"manual_rate": True, "manual_conversion_rate": 60.0}
        )
        self.assertAlmostEqual(invoice.manual_conversion_rate, 60.0)

    def test_a_rate_value_without_the_manual_rate_enabled_has_no_effect(self):
        invoice = self.env["account.move"].create(self._invoice_values())
        invoice.with_user(self.invoicing_user).write({"manual_conversion_rate": 70.0})
        self.assertFalse(invoice.manual_rate_active)
        self.assertAlmostEqual(invoice.invoice_currency_rate, 1 / 50.0)

    def test_invoicing_user_edits_a_manual_rate_document_without_touching_the_rate(self):
        invoice = self.env["account.move"].create(
            self._invoice_values(manual_rate=True, manual_conversion_rate=60.0)
        )
        invoice.with_user(self.invoicing_user).write(
            {"invoice_line_ids": [Command.update(invoice.invoice_line_ids.id, {"price_unit": 200.0})]}
        )
        self.assertTrue(invoice.manual_rate_active)
        self.assertAlmostEqual(self._get_payment_term_line(invoice).debit, 12000.0)

    def test_posted_documents_still_reject_the_change_for_allowed_users(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        for user in (self.manager_user, self.settings_user):
            with self.subTest(user=user.login):
                with self._assert_error(UserError, "cannot modify the manual rate"):
                    invoice.with_user(user).manual_conversion_rate = 70.0

    # ------------------------------------------------- inherited manual rates

    def test_invoicing_user_creates_a_credit_note_that_keeps_the_manual_rate(self):
        for move_type in ("out_invoice", "in_invoice"):
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(
                    self.usd, 100.0, self.rate_date_invoice, move_type, manual_rate=60.0
                )
                credit_note = self._reverse(self.invoicing_user, invoice)
                self.assertTrue(credit_note.manual_rate_active)
                self.assertAlmostEqual(credit_note.manual_conversion_rate, 60.0)
                self.assertAlmostEqual(credit_note.invoice_currency_rate, 1 / 60.0)

    def test_invoicing_user_reverses_an_entry_that_keeps_the_manual_rate(self):
        entry = self._create_entry(
            [
                (self.company_data["default_account_expense"], self.usd, 100.0),
                (self.company_data["default_account_revenue"], self.usd, -100.0),
            ],
            manual_rate=60.0,
        )
        reversal = self._reverse(self.invoicing_user, entry)
        self.assertTrue(reversal.manual_rate_active)
        self.assertAlmostEqual(reversal.manual_conversion_rate, 60.0)

    def test_a_reversal_only_carries_the_rate_of_the_document_it_reverses(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        values = self._invoice_values(
            "out_refund",
            reversed_entry_id=invoice.id,
            manual_rate=True,
            manual_conversion_rate=60.0,
        )
        credit_note = self.env["account.move"].with_user(self.invoicing_user).create(values)
        self.assertAlmostEqual(credit_note.manual_conversion_rate, 60.0)
        with self._assert_error(AccessError, ACCESS_ERROR):
            self.env["account.move"].with_user(self.invoicing_user).create(
                {**values, "manual_conversion_rate": 61.0}
            )

    def test_invoicing_user_posts_and_edits_the_payment_of_an_administrator(self):
        # The entry of a draft payment is created when it is posted, by the user who
        # posts it, and it carries the manual rate that an administrator captured.
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, "inbound", manual_rate=60.0, post=False
        )
        self.assertFalse(payment.move_id)
        payment.with_user(self.invoicing_user).write({"amount": 120.0})
        payment.with_user(self.invoicing_user).action_post()
        self.assertTrue(payment.move_id.manual_rate)
        self.assertAlmostEqual(payment.move_id.manual_conversion_rate, 60.0)
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, 7200.0)

        payment.with_user(self.invoicing_user).action_draft()
        payment.with_user(self.invoicing_user).write({"amount": 150.0})
        self.assertTrue(payment.move_id.manual_rate)
        self.assertAlmostEqual(payment._seek_for_lines()[0].balance, 9000.0)

    def test_the_entry_of_a_payment_only_carries_the_rate_of_its_payment(self):
        payment = self._create_direct_payment(
            self.usd, 100.0, self.rate_date_invoice, "inbound", manual_rate=60.0
        )
        payment.action_draft()
        entry = payment.move_id
        self.assertEqual(entry.state, "draft")
        entry.manual_rate = False
        carried = {"manual_rate": True, "manual_conversion_rate": 60.0}
        with self._assert_error(AccessError, ACCESS_ERROR):
            entry.with_user(self.invoicing_user).write(
                {**carried, "manual_conversion_rate": 61.0}
            )
        entry.with_user(self.invoicing_user).write(carried)
        self.assertTrue(entry.manual_rate)
        self.assertAlmostEqual(entry.manual_conversion_rate, 60.0)

    # ----------------------------------------------------------------- wizard

    def test_wizard_requires_the_rights_to_capture_the_rate(self):
        invoice = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "out_invoice"
        )
        with self._assert_error(AccessError, ACCESS_ERROR):
            self._wizard(
                self.invoicing_user,
                invoice,
                manual_rate=True,
                manual_conversion_rate=60.0,
            )
        wizard = self._wizard(self.invoicing_user, invoice, currency_id=self.usd.id)
        payment = wizard._create_payments()
        self.assertFalse(payment.manual_rate)

    def test_administrators_capture_the_rate_in_the_wizard(self):
        for user in (self.manager_user, self.settings_user):
            with self.subTest(user=user.login):
                invoice = self._create_invoice(
                    self.usd, 100.0, self.rate_date_invoice, "out_invoice"
                )
                wizard = self._wizard(
                    user,
                    invoice,
                    currency_id=self.usd.id,
                    manual_rate=True,
                    manual_conversion_rate=60.0,
                )
                payment = wizard._create_payments()
                self.assertTrue(payment.manual_rate)
                self.assertAlmostEqual(payment.manual_conversion_rate, 60.0)
