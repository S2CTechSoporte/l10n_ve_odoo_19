from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestVenezuelaDemoData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ves_company = cls.env.ref('l10n_ve_full.company_my_company_ves')
        cls.usd_company = cls.env.ref('l10n_ve_full.company_my_company_usd')

    def test_demo_companies_have_venezuelan_rif_and_currencies(self):
        for company, currency in (
            (self.ves_company, self.env.ref('base.VES')),
            (self.usd_company, self.env.ref('base.USD')),
        ):
            self.assertEqual(company.country_id, self.env.ref('base.ve'))
            self.assertEqual(company.currency_id, currency)
            self.assertEqual(company.currency_l10n_id, currency)
            validated_vat, country_code = self.env['res.partner']._run_vat_checks(
                self.env.ref('base.ve'), company.vat,
            )
            self.assertEqual(validated_vat, company.vat)
            self.assertEqual(country_code, 'VE')
            self.assertTrue(company.vat.startswith('J'))

    def test_demo_sales_purchases_inventory_and_invoices(self):
        cases = (
            {
                'company': self.ves_company,
                'sale': 'l10n_ve_full.sale_order_my_company_ves',
                'purchase': 'l10n_ve_full.purchase_order_my_company_ves',
                'picking': 'l10n_ve_full.picking_my_company_ves',
                'out_invoice': 'l10n_ve_full.invoice_my_company_ves',
                'in_invoice': 'l10n_ve_full.vendor_bill_my_company_ves',
            },
            {
                'company': self.usd_company,
                'sale': 'l10n_ve_full.sale_order_my_company_usd',
                'purchase': 'l10n_ve_full.purchase_order_my_company_usd',
                'picking': 'l10n_ve_full.picking_my_company_usd',
                'out_invoice': 'l10n_ve_full.invoice_my_company_usd',
                'in_invoice': 'l10n_ve_full.vendor_bill_my_company_usd',
            },
        )
        for case in cases:
            company = case['company']
            sale = self.env.ref(case['sale'])
            purchase = self.env.ref(case['purchase'])
            picking = self.env.ref(case['picking'])
            out_invoice = self.env.ref(case['out_invoice'])
            in_invoice = self.env.ref(case['in_invoice'])

            self.assertEqual(sale.company_id, company)
            self.assertEqual(sale.currency_id, company.currency_id)
            self.assertEqual(len(sale.order_line), 1)

            self.assertEqual(purchase.company_id, company)
            self.assertEqual(purchase.currency_id, company.currency_id)
            self.assertEqual(len(purchase.order_line), 1)

            self.assertEqual(picking.picking_type_id.company_id, company)
            self.assertEqual(picking.location_id.warehouse_id, picking.picking_type_id.warehouse_id)
            self.assertEqual(len(picking.move_ids), 1)

            for invoice, move_type in ((out_invoice, 'out_invoice'), (in_invoice, 'in_invoice')):
                self.assertEqual(invoice.company_id, company)
                self.assertEqual(invoice.currency_id, company.currency_id)
                self.assertEqual(invoice.move_type, move_type)
                self.assertEqual(invoice.state, 'draft')
                self.assertEqual(len(invoice.invoice_line_ids), 1)
                self.assertIn(company, invoice.invoice_line_ids.account_id.company_ids)
                self.assertTrue(invoice.invoice_line_ids.tax_ids)