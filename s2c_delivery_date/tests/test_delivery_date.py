# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestDeliveryDate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env['res.partner'].create({
            'name': 'EMPRENDIMIENTO TEST',
            'customer_rank': 1,
        })
        cls.vendor = cls.env['res.partner'].create({
            'name': 'PROVEEDOR TEST',
            'supplier_rank': 1,
        })

        cls.payment_term_30 = cls.env.ref('account.account_payment_term_30days')
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'sale')
        ], limit=1)
        cls.purchase_journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase')
        ], limit=1)

        cls.income_account = cls.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_ids', 'child_of', cls.env.company.id),
        ], limit=1)
        cls.expense_account = cls.env['account.account'].search([
            ('account_type', 'in', ('expense', 'expense_direct_cost', 'expense_depreciation')),
            ('company_ids', 'child_of', cls.env.company.id),
        ], limit=1)
        cls.sale_tax = cls.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        cls.purchase_tax = cls.env['account.tax'].search([
            ('type_tax_use', '=', 'purchase'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        cls.account_dual_currency_installed = bool(cls.env['ir.module.module'].search([
            ('name', '=', 'account_dual_currency'),
            ('state', '=', 'installed'),
        ], limit=1))

        cls.assertTrue(cls.journal, "A sale journal is required for s2c_delivery_date tests")
        cls.assertTrue(cls.purchase_journal, "A purchase journal is required for s2c_delivery_date tests")
        cls.assertTrue(cls.income_account, "An income account is required for s2c_delivery_date tests")
        cls.assertTrue(cls.expense_account, "An expense account is required for s2c_delivery_date tests")

    def _create_invoice(self, invoice_date, delivery_date, payment_term):
        invoice_line_vals = {
            'name': 'Delivery date test line',
            'quantity': 1.0,
            'price_unit': 100.0,
            'account_id': self.income_account.id,
        }
        if self.sale_tax:
            invoice_line_vals['tax_ids'] = [(6, 0, self.sale_tax.ids)]

        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.journal.id,
            'invoice_date': invoice_date,
            'delivery_date': delivery_date,
            'invoice_payment_term_id': payment_term.id,
            'invoice_line_ids': [(0, 0, invoice_line_vals)],
        })

    def _create_vendor_bill(self, invoice_date, delivery_date, payment_term):
        invoice_line_vals = {
            'name': 'Delivery date vendor bill line',
            'quantity': 1.0,
            'price_unit': 100.0,
            'account_id': self.expense_account.id,
        }
        if self.purchase_tax:
            invoice_line_vals['tax_ids'] = [(6, 0, self.purchase_tax.ids)]

        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'journal_id': self.purchase_journal.id,
            'invoice_date': invoice_date,
            'delivery_date': delivery_date,
            'invoice_payment_term_id': payment_term.id,
            'invoice_line_ids': [(0, 0, invoice_line_vals)],
        })

    def _get_aged_report_options(self, report_xmlid, date_to):
        report = self.env.ref(report_xmlid)
        return report.get_options({
            'selected_variant_id': report.id,
            'date': {
                'date_from': fields.Date.to_string(date_to),
                'date_to': fields.Date.to_string(date_to),
                'mode': 'range',
                'filter': 'custom',
            },
            'show_account': True,
            'show_currency': True,
        })

    def _get_aged_receivable_options(self, date_to):
        return self._get_aged_report_options('account_reports.aged_receivable_report', date_to)

    def _get_aged_payable_options(self, date_to):
        return self._get_aged_report_options('account_reports.aged_payable_report', date_to)

    def test_01_invoice_date_due_with_delivery_date(self):
        invoice_date = fields.Date.today()
        delivery_date = invoice_date + timedelta(days=10)
        expected_due_date = delivery_date + timedelta(days=30)

        invoice = self._create_invoice(invoice_date, delivery_date, self.payment_term_30)

        self.assertEqual(
            invoice.invoice_date_due,
            expected_due_date,
            "invoice_date_due should be computed from delivery_date",
        )

    def test_02_date_maturity_matches_invoice_date_due(self):
        invoice_date = fields.Date.today()
        delivery_date = invoice_date + timedelta(days=10)

        invoice = self._create_invoice(invoice_date, delivery_date, self.payment_term_30)
        invoice.action_post()

        receivable_lines = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )

        for line in receivable_lines:
            self.assertEqual(
                line.date_maturity,
                invoice.invoice_date_due,
                "date_maturity should match invoice_date_due after posting",
            )

    def test_03_delivery_time_calculation(self):
        invoice_date = fields.Date.today()
        delivery_date = invoice_date + timedelta(days=10)

        invoice = self._create_invoice(invoice_date, delivery_date, self.payment_term_30)

        self.assertEqual(
            invoice.delivery_time,
            10,
            "delivery_time should be the number of days between invoice and delivery dates",
        )

    def test_04_invoice_without_delivery_date(self):
        invoice_date = fields.Date.today()
        expected_due_date = invoice_date + timedelta(days=30)

        invoice = self._create_invoice(invoice_date, invoice_date, self.payment_term_30)

        self.assertEqual(
            invoice.invoice_date_due,
            expected_due_date,
            "invoice_date_due should still follow invoice_date when delivery_date is the same",
        )

        self.assertEqual(
            invoice.delivery_time,
            0,
            "delivery_time should be zero when delivery_date matches invoice_date",
        )

    def test_05_needed_terms_uses_delivery_date(self):
        invoice_date = fields.Date.today()
        delivery_date = invoice_date + timedelta(days=10)
        expected_maturity = delivery_date + timedelta(days=30)

        invoice = self._create_invoice(invoice_date, delivery_date, self.payment_term_30)

        self.assertTrue(invoice.needed_terms, "needed_terms no debería estar vacío")

        for key in invoice.needed_terms.keys():
            if key:
                self.assertEqual(
                    key.get('date_maturity'),
                    expected_maturity,
                    "needed_terms should use delivery_date as the payment term reference",
                )

    def test_06_update_delivery_date_recalculates_due_date(self):
        invoice_date = fields.Date.today()
        delivery_date_1 = invoice_date + timedelta(days=5)
        delivery_date_2 = invoice_date + timedelta(days=15)

        invoice = self._create_invoice(invoice_date, delivery_date_1, self.payment_term_30)

        due_date_1 = invoice.invoice_date_due
        expected_due_1 = delivery_date_1 + timedelta(days=30)

        self.assertEqual(due_date_1, expected_due_1, "The initial due date is incorrect")

        invoice.write({'delivery_date': delivery_date_2})

        due_date_2 = invoice.invoice_date_due
        expected_due_2 = delivery_date_2 + timedelta(days=30)

        self.assertEqual(
            due_date_2,
            expected_due_2,
            "Changing delivery_date should recompute invoice_date_due",
        )
        self.assertNotEqual(
            due_date_1,
            due_date_2,
            "invoice_date_due did not change after updating delivery_date",
        )

    def test_07_posted_invoice_consistency(self):
        invoice_date = fields.Date.today()
        delivery_date = invoice_date + timedelta(days=10)

        invoice = self._create_invoice(invoice_date, delivery_date, self.payment_term_30)
        invoice.action_post()

        receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == 'asset_receivable'
        )[0]

        if invoice.invoice_date_due and receivable_line.date_maturity:
            days_diff = abs((invoice.invoice_date_due - receivable_line.date_maturity).days)

            self.assertEqual(
                days_diff,
                0,
                "Posted invoices should keep invoice_date_due and date_maturity aligned",
            )

    def test_08_aged_receivable_report_renders_with_custom_columns(self):
        invoice_date = fields.Date.today()
        delivery_date = invoice_date + timedelta(days=10)

        invoice = self._create_invoice(invoice_date, delivery_date, self.payment_term_30)
        invoice.action_post()

        report = self.env.ref('account_reports.aged_receivable_report')
        options = self._get_aged_receivable_options(invoice.invoice_date_due)
        report_information = report.get_report_information(options)

        self.assertIn('lines', report_information)
        self.assertTrue(report_information['lines'], "The aged receivable report should return lines")

        expression_labels = {
            column['expression_label']
            for column in options['columns']
        }
        self.assertTrue(
            {'delivery_date', 'delivery_time', 'invoice_date_due', 'remaining_days'}.issubset(expression_labels),
            "The aged receivable report should include the custom delivery-date columns",
        )

    def test_09_aged_payable_report_renders(self):
        invoice_date = fields.Date.today()
        delivery_date = invoice_date + timedelta(days=10)

        bill = self._create_vendor_bill(invoice_date, delivery_date, self.payment_term_30)
        bill.action_post()

        report = self.env.ref('account_reports.aged_payable_report')
        options = self._get_aged_payable_options(bill.invoice_date_due)
        report_information = report.get_report_information(options)

        self.assertIn('lines', report_information)
        self.assertTrue(report_information['lines'], "The aged payable report should return lines")

        expression_labels = {
            column['expression_label']
            for column in options['columns']
        }
        self.assertFalse(
            {'delivery_date', 'delivery_time', 'invoice_date_due', 'remaining_days'} & expression_labels,
            "The aged payable report should not receive receivable-only delivery columns",
        )

        if self.account_dual_currency_installed:
            self.assertTrue(
                {'fcurrency', 'total_fcurrency'}.issubset(expression_labels),
                "The aged payable report should preserve account_dual_currency columns when installed",
            )
