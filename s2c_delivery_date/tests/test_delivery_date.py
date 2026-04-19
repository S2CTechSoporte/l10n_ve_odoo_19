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

        cls.payment_term_30 = cls.env.ref('account.account_payment_term_30days')
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'sale')
        ], limit=1)

        cls.income_account = cls.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_ids', 'child_of', cls.env.company.id),
        ], limit=1)
        cls.sale_tax = cls.env['account.tax'].search([
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)

        cls.assertTrue(cls.journal, "A sale journal is required for s2c_delivery_date tests")
        cls.assertTrue(cls.income_account, "An income account is required for s2c_delivery_date tests")

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
