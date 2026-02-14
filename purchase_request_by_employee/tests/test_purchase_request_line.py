from odoo.tests.common import TransactionCase


class TestPurchaseRequestLine(TransactionCase):

    def test_onchange_product_id_domain_uom_compatibility(self):
        uom_unit = self.env.ref('uom.product_uom_unit')
        uom_kgm = self.env.ref('uom.product_uom_kgm')

        product = self.env['product.product'].create({
            'name': 'Producto prueba UoM',
            'type': 'consu',
            'purchase_ok': True,
            'uom_id': uom_unit.id,
        })

        line = self.env['purchase.request.line'].new({'product_id': product.id})
        result = line.onchange_product_id()

        domain = result.get('domain', {}).get('product_uom')
        self.assertTrue(domain)

        allowed_uoms = self.env['uom.uom'].search(domain)
        self.assertIn(uom_unit, allowed_uoms)
        self.assertNotIn(uom_kgm, allowed_uoms)
        self.assertTrue(all(uom._has_common_reference(uom_unit) for uom in allowed_uoms))
