from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFiscalDocumentRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.ve_country = cls.env.ref('base.ve')
        cls.us_country = cls.env.ref('base.us')
        cls.ve_person_without_document = cls.Partner.create({
            'name': 'Venezuelan Person Without Document',
            'company_type': 'person',
            'country_id': cls.ve_country.id,
        })
        cls.foreign_person_without_document = cls.Partner.create({
            'name': 'Foreign Person Without Document',
            'company_type': 'person',
            'country_id': cls.us_country.id,
        })
        cls.ve_company_without_rif = cls.Partner.create({
            'name': 'Venezuelan Company Without RIF',
            'company_type': 'company',
            'country_id': cls.ve_country.id,
        })
        cls.foreign_company_without_rif = cls.Partner.create({
            'name': 'Foreign Company Without RIF',
            'company_type': 'company',
            'country_id': cls.us_country.id,
        })

    def test_sale_order_requires_document_only_for_venezuelan_partners(self):
        SaleOrder = self.env['sale.order']

        with self.assertRaises(UserError):
            SaleOrder.create({'partner_id': self.ve_person_without_document.id})
        with self.assertRaises(UserError):
            SaleOrder.create({'partner_id': self.ve_company_without_rif.id})

        foreign_person_order = SaleOrder.create({
            'partner_id': self.foreign_person_without_document.id,
        })
        foreign_company_order = SaleOrder.create({
            'partner_id': self.foreign_company_without_rif.id,
        })
        self.assertEqual(foreign_person_order.partner_id, self.foreign_person_without_document)
        self.assertEqual(foreign_company_order.partner_id, self.foreign_company_without_rif)

        with self.assertRaises(UserError):
            foreign_person_order.write({'partner_id': self.ve_person_without_document.id})

    def test_purchase_order_requires_document_only_for_venezuelan_partners(self):
        PurchaseOrder = self.env['purchase.order']

        with self.assertRaises(UserError):
            PurchaseOrder.create({'partner_id': self.ve_person_without_document.id})
        with self.assertRaises(UserError):
            PurchaseOrder.create({'partner_id': self.ve_company_without_rif.id})

        foreign_person_order = PurchaseOrder.create({
            'partner_id': self.foreign_person_without_document.id,
        })
        foreign_company_order = PurchaseOrder.create({
            'partner_id': self.foreign_company_without_rif.id,
        })
        self.assertEqual(foreign_person_order.partner_id, self.foreign_person_without_document)
        self.assertEqual(foreign_company_order.partner_id, self.foreign_company_without_rif)

        with self.assertRaises(UserError):
            foreign_person_order.write({'partner_id': self.ve_person_without_document.id})

    def test_account_move_requires_document_only_for_venezuelan_partners(self):
        AccountMove = self.env['account.move']
        move = AccountMove.create({
            'move_type': 'out_invoice',
            'partner_id': self.foreign_person_without_document.id,
        })

        move.write({'partner_id': self.foreign_person_without_document.id})
        move.write({'partner_id': self.foreign_company_without_rif.id})

        with self.assertRaises(UserError):
            move.write({'partner_id': self.ve_person_without_document.id})
        with self.assertRaises(UserError):
            move.write({'partner_id': self.ve_company_without_rif.id})