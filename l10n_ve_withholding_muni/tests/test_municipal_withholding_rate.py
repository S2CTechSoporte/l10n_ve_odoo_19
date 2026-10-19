from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestMunicipalWithholdingInvoiceRate(AccountTestInvoicingCommon):
    """The municipal withholding of an invoice takes the rate of the invoice.

    The rate is the standard ``invoice_currency_rate`` of Odoo: a draft invoice gets it
    edited by hand here, as an accountant (or any other module) does.
    """

    country_code = 'DE'
    chart_template = 'generic_coa'
    # Units of the invoice currency (VES) per unit of the company currency (USD).
    system_rate = 800.0
    invoice_rate = 880.0
    foreign_base = 88000.0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.env.user.group_ids |= cls.env.ref('l10n_ve_full.group_localizacion')
        cls.usd = cls.env.ref('base.USD')
        cls.ves = cls.env.ref('base.VES')
        (cls.usd | cls.ves).active = True
        cls.company.currency_id = cls.usd
        cls.invoice_date = fields.Date.to_date('2026-01-10')
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.ves.id),
            ('company_id', '=', cls.company.id),
        ]).unlink()
        cls.env['res.currency.rate'].create({
            'company_id': cls.company.id,
            'currency_id': cls.ves.id,
            'name': cls.invoice_date,
            'rate': cls.system_rate,
        })
        cls.company.write({
            'muni_wh_agent': True,
            'purchase_jrl_id': cls.company_data['default_journal_misc'].id,
            'account_ret_muni_receivable_id': cls.company_data['default_account_receivable'].id,
            'account_ret_muni_payable_id': cls.company_data['default_account_payable'].id,
        })
        # The municipal withholding is the only one that this test creates.
        cls.company.partner_id.write({'wh_iva_agent': False, 'islr_withholding_agent': False})
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Municipal Withholding Vendor',
            'country_id': cls.env.ref('base.de').id,
            'wh_iva_agent': False,
            'islr_withholding_agent': False,
        })
        cls.concept = cls.env.ref('l10n_ve_withholding_muni.concept2')
        cls.bill_count = 0

    def _create_bill(self, currency=None, amount=None, invoice_rate=None):
        self.bill_count += 1
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'invoice_date': self.invoice_date,
            'date': self.invoice_date,
            'journal_id': self.company_data['default_journal_purchase'].id,
            'currency_id': (currency or self.ves).id,
            'supplier_invoice_number': 'SUP-%s' % self.bill_count,
            'nro_ctrl': 'CTRL-%s' % self.bill_count,
            'invoice_line_ids': [Command.create({
                'name': 'Municipal line',
                'quantity': 1.0,
                'price_unit': amount or self.foreign_base,
                'wh_concept_id': self.concept.id,
                'tax_ids': [Command.clear()],
            })],
        })
        if invoice_rate:
            bill.invoice_currency_rate = invoice_rate
        bill.action_post()
        return bill

    def test_module_does_not_depend_on_the_dual_currency_module(self):
        """The withholdings only use standard fields of Odoo: the modules are independent."""
        module = self.env['ir.module.module'].search([('name', '=', 'l10n_ve_withholding_muni')])
        self.assertTrue(module)
        self.assertNotIn('accounting_dual_currency', module.dependencies_id.mapped('name'))

    def test_conversion_uses_the_rate_of_the_invoice(self):
        system = self._create_bill()
        manual = self._create_bill(invoice_rate=self.invoice_rate)
        self.assertAlmostEqual(system.conv_div_nac(self.foreign_base), self.foreign_base / self.system_rate)
        self.assertAlmostEqual(manual.conv_div_nac(self.foreign_base), self.foreign_base / self.invoice_rate)

    def test_conversion_of_an_invoice_in_the_company_currency_keeps_the_amount(self):
        bill = self._create_bill(currency=self.usd, amount=100.0)
        self.assertEqual(bill.conv_div_nac(123.456), 123.456)

    def test_voucher_base_uses_the_rate_of_the_invoice(self):
        bill = self._create_bill(invoice_rate=self.invoice_rate)
        voucher = bill.wh_muni_id
        self.assertTrue(voucher)
        base = self.foreign_base / self.invoice_rate
        self.assertAlmostEqual(voucher.act_code_ids.base_tax, base, places=2)
        self.assertAlmostEqual(voucher.withheld_amount, base, places=2)
        self.assertAlmostEqual(voucher.amount, base * self.concept.aliquot / 100.0, places=2)
        # The rate of the table of the date would give another base.
        self.assertNotAlmostEqual(
            voucher.act_code_ids.base_tax, self.foreign_base / self.system_rate, places=2)

    def test_voucher_entry_is_expressed_at_the_rate_of_the_invoice(self):
        bill = self._create_bill(invoice_rate=self.invoice_rate)
        voucher = bill.wh_muni_id
        voucher.action_post()
        entry = voucher.wh_muni_id
        self.assertEqual(entry.state, 'posted')
        self.assertEqual(len(entry.line_ids), 2)
        withheld = voucher.amount
        self.assertGreater(withheld, 0.0)
        for line in entry.line_ids:
            self.assertEqual(line.currency_id, self.ves)
            self.assertAlmostEqual(abs(line.balance), withheld, places=2)
            self.assertAlmostEqual(
                abs(line.amount_currency), self.ves.round(withheld * self.invoice_rate))
            self.assertGreater(line.amount_currency * line.balance, 0)

    def test_voucher_entry_of_an_invoice_in_the_company_currency_keeps_company_currency(self):
        bill = self._create_bill(currency=self.usd, amount=100.0)
        voucher = bill.wh_muni_id
        voucher.action_post()
        entry = voucher.wh_muni_id
        self.assertEqual(entry.line_ids.currency_id, self.usd)
        self.assertAlmostEqual(sum(entry.line_ids.mapped('debit')), voucher.amount, places=2)
