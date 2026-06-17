from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestMunicipalWithholding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.month = cls.env.ref('l10n_ve_withholding_muni.month6')
        cls.year = cls.env.ref('l10n_ve_withholding_muni.year27')
        cls.wh_concept = cls.env.ref('l10n_ve_withholding_muni.concept2')

        cls.receivable_account = cls.env['account.account'].search([
            ('account_type', '=', 'asset_receivable'),
        ], limit=1)
        cls.payable_account = cls.env['account.account'].search([
            ('account_type', '=', 'liability_payable'),
        ], limit=1)
        cls.expense_account = cls.env['account.account'].search([
            ('account_type', 'in', ['expense', 'expense_direct_cost']),
        ], limit=1)
        cls.general_journal = cls.env['account.journal'].search([
            ('type', '=', 'general'),
        ], limit=1)
        cls.purchase_journal = cls.env['account.journal'].search([
            ('type', '=', 'purchase'),
        ], limit=1)
        cls.tax_group = cls.env['account.tax.group'].create({
            'name': 'Municipal Withholding Test Tax Group',
        })
        cls.purchase_tax = cls.env['account.tax'].create({
            'name': 'Municipal Withholding Purchase VAT 16%',
            'amount_type': 'percent',
            'amount': 16.0,
            'type_tax_use': 'purchase',
            'tax_group_id': cls.tax_group.id,
            'type_tax': 'iva',
            'appl_type': 'general',
        })

        assert cls.receivable_account
        assert cls.payable_account
        assert cls.expense_account
        assert cls.general_journal
        assert cls.purchase_journal

        cls.partner = cls.env['res.partner'].create({
            'name': 'Municipal Withholding Supplier',
            'company_type': 'company',
            'supplier_rank': 1,
            'vat': 'J-87654321-3',
            'street': 'Av. Principal',
            'city': 'Machiques',
            'property_account_receivable_id': cls.receivable_account.id,
            'property_account_payable_id': cls.payable_account.id,
        })

        cls.company.write({
            'muni_wh_agent': True,
            'purchase_jrl_id': cls.general_journal.id,
            'account_ret_muni_receivable_id': cls.receivable_account.id,
            'account_ret_muni_payable_id': cls.payable_account.id,
        })

    def _bill_values(self):
        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.purchase_journal.id,
            'invoice_date': fields.Date.from_string('2026-06-17'),
            'date': fields.Date.from_string('2026-06-17'),
            'invoice_line_ids': [
                (0, 0, {
                    'name': 'Municipal line A',
                    'account_id': self.expense_account.id,
                    'quantity': 1.0,
                    'price_unit': 120.0,
                    'wh_concept_id': self.wh_concept.id,
                    'tax_ids': [(6, 0, [self.purchase_tax.id])],
                }),
                (0, 0, {
                    'name': 'Municipal line B',
                    'account_id': self.expense_account.id,
                    'quantity': 1.0,
                    'price_unit': 80.0,
                    'wh_concept_id': self.wh_concept.id,
                    'tax_ids': [(6, 0, [self.purchase_tax.id])],
                }),
            ],
        }
        if 'supplier_invoice_number' in self.env['account.move']._fields:
            invoice_vals['supplier_invoice_number'] = 'SUP-001'
        if 'nro_ctrl' in self.env['account.move']._fields:
            invoice_vals['nro_ctrl'] = 'CTRL-001'
        return invoice_vals

    def test_manual_voucher_keeps_name_and_computes_totals(self):
        voucher = self.env['municipality.tax'].create({
            'name': 'MUNI-MANUAL-0001',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'transaction_date': fields.Date.from_string('2026-06-17'),
            'date_start': self.month.id,
            'date_end': self.year.id,
            'act_code_ids': [
                (0, 0, {
                    'wh_concept_id': self.wh_concept.id,
                    'code': self.wh_concept.code,
                    'aliquot': self.wh_concept.aliquot,
                    'base_tax': 100.0,
                }),
                (0, 0, {
                    'wh_concept_id': self.wh_concept.id,
                    'code': self.wh_concept.code,
                    'aliquot': self.wh_concept.aliquot,
                    'base_tax': 50.0,
                }),
            ],
        })

        self.assertEqual(voucher.name, 'MUNI-MANUAL-0001')
        self.assertAlmostEqual(voucher.withheld_amount, 150.0)
        self.assertAlmostEqual(voucher.amount, 1.5)

    def test_post_vendor_bill_creates_voucher(self):
        bill = self.env['account.move'].create(self._bill_values())

        bill.action_post()

        voucher = bill.wh_muni_id
        self.assertTrue(voucher)
        self.assertEqual(voucher.partner_id, self.partner)
        self.assertEqual(voucher.state, 'draft')
        self.assertTrue(voucher.name.startswith('202606'))
        self.assertAlmostEqual(voucher.withheld_amount, 200.0)
        self.assertAlmostEqual(voucher.amount, 2.0)
        self.assertEqual(len(voucher.act_code_ids), 1)
        self.assertAlmostEqual(voucher.act_code_ids.base_tax, 200.0)
        self.assertAlmostEqual(voucher.act_code_ids.wh_amount, 2.0)

    def test_action_post_requires_transaction_date(self):
        voucher = self.env['municipality.tax'].create({
            'name': 'MUNI-ERROR-0001',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
            'transaction_date': False,
            'date_start': self.month.id,
            'date_end': self.year.id,
        })

        with self.assertRaises(ValidationError):
            voucher.action_post()