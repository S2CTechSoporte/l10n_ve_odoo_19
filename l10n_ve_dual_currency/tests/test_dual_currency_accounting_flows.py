from odoo.tests import Form, tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestDualCurrencyAccountingFlows(DualCurrencyTestCommon):
    def _create_credit_note(self, invoice, reversal_date):
        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create(
            {
                "move_ids": [(6, 0, invoice.ids)],
                "company_id": self.company.id,
                "journal_id": invoice.journal_id.id,
                "date": reversal_date,
                "reason": "Venezuela dual currency reversal test",
            }
        )
        wizard.refund_moves()
        credit_note = wizard.new_move_ids[:1]
        if credit_note.state == "draft":
            credit_note.action_post()
        return credit_note

    def test_ves_credit_note_reuses_original_invoice_rate(self):
        invoice = self._create_invoice(
            self.ves,
            5000.0,
            self.rate_date_invoice,
        )
        credit_note = self._create_credit_note(invoice, self.rate_date_third)
        credit_line = credit_note.invoice_line_ids[:1]
        term_line = self._get_payment_term_line(credit_note)

        self.assertAlmostEqual(credit_line.conversion_rate, 50.0, places=2)
        self.assertAlmostEqual(abs(credit_line.balance_fcurrency), 100.0, places=2)
        self.assertAlmostEqual(abs(term_line.balance_fcurrency), 100.0, places=2)
        self.assertAlmostEqual(credit_note.amount_total_fcurrency, 100.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual_fcurrency, 0.0, places=2)

    def test_usd_credit_note_uses_reversal_date(self):
        invoice = self._create_invoice(
            self.usd,
            100.0,
            self.rate_date_invoice,
        )
        credit_note = self._create_credit_note(invoice, self.rate_date_third)
        credit_line = credit_note.invoice_line_ids[:1]

        self.assertAlmostEqual(credit_line.conversion_rate, 54.0, places=2)
        self.assertAlmostEqual(abs(credit_line.balance_fcurrency), 100.0, places=2)
        self.assertAlmostEqual(
            credit_note.amount_total_local_currency,
            5400.0,
            places=2,
        )

    def test_manual_usd_entry_keeps_ves_and_reference_balances(self):
        move_form = Form(
            self.env["account.move"].with_context(
                default_move_type="entry",
                default_journal_id=self.misc_journal.id,
            )
        )
        move_form.date = self.rate_date_invoice
        move_form.journal_id = self.misc_journal
        with move_form.line_ids.new() as debit_line:
            debit_line.name = "USD debit"
            debit_line.account_id = self.company_data["default_account_expense"]
            debit_line.currency_id = self.usd
            debit_line.amount_currency = 200.0
        with move_form.line_ids.new() as credit_line:
            credit_line.name = "USD credit"
            credit_line.account_id = self.company_data["default_account_revenue"]
            credit_line.currency_id = self.usd
            credit_line.amount_currency = -200.0

        move = move_form.save()
        foreign_lines = move.line_ids.filtered(lambda line: line.currency_id == self.usd)
        self.assertEqual(len(foreign_lines), 2)
        self.assertEqual(
            sorted(self.ves.round(abs(line.balance)) for line in foreign_lines),
            [10000.0, 10000.0],
        )
        self.assertEqual(
            sorted(self.usd.round(abs(line.balance_fcurrency)) for line in foreign_lines),
            [200.0, 200.0],
        )

    def test_missing_reference_currency_falls_back_to_ves(self):
        self.company.fcurrency_id = False
        invoice = self._create_invoice(
            self.ves,
            5000.0,
            self.rate_date_invoice,
        )
        self.assertFalse(invoice.fcurrency_id)
        self.assertAlmostEqual(invoice.amount_total_fcurrency, 5000.0, places=2)
        self.assertAlmostEqual(invoice.amount_residual_fcurrency, 5000.0, places=2)
        self.assertAlmostEqual(
            abs(self._get_payment_term_line(invoice).balance_fcurrency),
            5000.0,
            places=2,
        )

    def test_venezuelan_currency_and_dependencies(self):
        self.assertTrue(self.ves.active)
        self.assertEqual(self.env.ref("base.ve").currency_id, self.ves)

        module = self.env["ir.module.module"].search(
            [("name", "=", "l10n_ve_dual_currency")],
            limit=1,
        )
        dependencies = set(module.dependencies_id.mapped("name"))
        self.assertIn("l10n_ve", dependencies)
        self.assertIn("account_reports", dependencies)
        self.assertNotIn("account_report_multi_currency", dependencies)
