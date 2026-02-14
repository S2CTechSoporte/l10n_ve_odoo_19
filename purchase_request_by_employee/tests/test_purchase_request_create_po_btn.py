from odoo.tests.common import TransactionCase


class TestPurchaseRequestCreatePoBtn(TransactionCase):

    def test_create_po_btn_creates_po_line(self):
        partner = self.env.user.partner_id
        uom_unit = self.env.ref('uom.product_uom_unit')
        product = self.env['product.product'].create({
            'name': 'Producto Test PO',
            'type': 'consu',
            'purchase_ok': True,
            'uom_id': uom_unit.id,
        })

        request = self.env['purchase.request'].create({
            'partner_id': partner.id,
            'line_ids': [(0, 0, {
                'name': 'Linea Test',
                'product_id': product.id,
                'product_qty': 2,
                'product_uom': uom_unit.id,
            })],
        })

        action = request.create_po_btn()
        self.assertTrue(action.get('res_id'))

        po = self.env['purchase.order'].browse(action['res_id'])
        self.assertTrue(po.exists())
        self.assertTrue(po.order_line)
        self.assertEqual(po.order_line[0].product_uom_id, product.uom_id)
