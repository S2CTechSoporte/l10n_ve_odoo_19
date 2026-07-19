from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResPartnerBusinessDocumentLock(TransactionCase):

    def test_partner_with_business_documents_can_modify_configuration_fields(self):
        partner = self.env['res.partner'].create({
            'name': 'Configurable Partner',
            'company_type': 'company',
        })

        with patch.object(
            type(partner),
            '_get_business_document_lock_reasons',
            return_value=['Ventas: 1', 'Facturado: 10.0', 'Compras: 2'],
        ):
            partner.write({'phone': '02121234567'})

        self.assertEqual(partner.phone, '02121234567')

    def test_partner_with_business_documents_cannot_modify_sensitive_fiscal_fields(self):
        partner = self.env['res.partner'].create({
            'name': 'Locked Partner',
            'company_type': 'company',
        })

        with patch.object(
            type(partner),
            '_get_business_document_lock_reasons',
            return_value=['Ventas: 1', 'Facturado: 10.0', 'Compras: 2'],
        ):
            with self.assertRaises(UserError) as error:
                partner.write({'name': 'Changed Partner', 'identification_id': '12345678'})

        message = str(error.exception)
        self.assertIn('No puede modificar los datos fiscales del contacto', message)
        self.assertIn('Campos bloqueados', message)
        self.assertIn('Nombre', message)
        self.assertIn('Documento de Identidad', message)
        self.assertIn('ventas, facturas o compras registradas', message)
        self.assertIn('Ventas: 1', message)
        self.assertIn('Facturado: 10.0', message)
        self.assertIn('Compras: 2', message)

    def test_partner_with_business_documents_can_open_form_read(self):
        partner = self.env['res.partner'].create({
            'name': 'Readable Locked Partner',
            'company_type': 'company',
        })

        with patch.object(
            type(partner),
            '_get_business_document_lock_reasons',
            return_value=['Ventas: 1'],
        ):
            values = partner.web_read({'name': {}})

        self.assertEqual(values[0]['name'], 'Readable Locked Partner')

    def test_partner_with_business_documents_allows_noop_sensitive_write(self):
        partner = self.env['res.partner'].create({
            'name': 'Noop Locked Partner',
            'company_type': 'company',
        })

        with patch.object(
            type(partner),
            '_get_business_document_lock_reasons',
            return_value=['Compras: 1'],
        ):
            partner.write({'name': partner.name})

        self.assertEqual(partner.name, 'Noop Locked Partner')

    def test_business_document_lock_reasons_use_smart_button_values(self):
        partner = self.env['res.partner'].new({'name': 'Locked Partner'})
        partner.sale_order_count = 1
        partner.total_invoiced = 10.0
        partner.purchase_order_count = 2

        reasons = partner._get_business_document_lock_reasons()

        self.assertEqual(reasons, ['Ventas: 1', 'Facturado: 10.0', 'Compras: 2'])