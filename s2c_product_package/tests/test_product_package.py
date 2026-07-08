# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestS2CProductPackage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')

        cls.product = cls.env['product.product'].create({
            'name': 'S2C Test Product Package',
            'type': 'consu',
            'is_storable': True,
            'uom_id': cls.uom_unit.id,
            'weight': 2.0,
            'volume': 1.5,
        })

        cls.packaging = cls.env['product.packaging'].create({
            'name': 'Caja x12',
            'product_id': cls.product.id,
            'product_uom_id': cls.uom_unit.id,
            'qty': 12.0,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'S2C Product Package Partner',
            'customer_rank': 1,
        })

        cls.sale_journal = cls.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        cls.income_account = cls.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_ids', 'child_of', cls.env.company.id),
        ], limit=1)

        cls.assertTrue(cls.sale_journal, 'A sale journal is required for product package tests')
        cls.assertTrue(cls.income_account, 'An income account is required for product package tests')

    def _create_move(self, quantity=12.0):
        return self.env['stock.move'].create({
            'product_id': self.product.id,
            'product_uom': self.uom_unit.id,
            'product_uom_qty': quantity,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'product_packaging_id': self.packaging.id,
            'description_picking': 'S2C packaging move',
        })

    def _create_done_move(self, quantity=12.0):
        self.env['stock.quant']._update_available_quantity(self.product, self.stock_location, quantity)

        move = self._create_move(quantity)
        move._action_confirm()
        move._action_assign()
        if not move.move_line_ids:
            self.env['stock.move.line'].create({
                'move_id': move.id,
                'product_id': self.product.id,
                'product_uom_id': self.uom_unit.id,
                'quantity': quantity,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'picked': True,
            })
        else:
            move.move_line_ids.write({'quantity': quantity, 'picked': True})

        move.picked = True
        move._action_done()
        self.env.flush_all()
        return move

    def test_01_packaging_liters_and_weight_compute(self):
        self.assertAlmostEqual(self.packaging.packaging_liters, 18.0, places=4)
        self.assertAlmostEqual(self.packaging.packaging_weight, 24.0, places=4)

    def test_02_stock_move_and_move_line_packaging_inverse(self):
        move = self._create_move(24.0)
        self.assertAlmostEqual(move.packaging_quantity, 2.0, places=4)

        move.packaging_quantity = 3.0
        self.assertAlmostEqual(move.product_uom_qty, 36.0, places=4)

        move_line = self.env['stock.move.line'].create({
            'move_id': move.id,
            'product_id': self.product.id,
            'product_uom_id': self.uom_unit.id,
            'quantity': 12.0,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
        })
        self.assertAlmostEqual(move_line.packaging_quantity, 1.0, places=4)

        move_line.packaging_quantity = 2.0
        self.assertAlmostEqual(move_line.quantity, 24.0, places=4)

    def test_03_product_and_quant_packaging_metrics(self):
        self.env['stock.quant']._update_available_quantity(self.product, self.stock_location, 24.0)

        self.product._compute_quantity_packaging()
        self.assertEqual(self.product.packaging_name, self.packaging.name)
        self.assertAlmostEqual(self.product.packaging_qty_available, 2.0, places=4)
        self.assertAlmostEqual(self.product.packaging_free_qty, 2.0, places=4)

        quant = self.env['stock.quant'].search([
            ('product_id', '=', self.product.id),
            ('location_id', '=', self.stock_location.id),
        ], limit=1)
        self.assertTrue(quant, 'A stock quant is required for quant packaging test')

        quant._compute_inventory_quantity_auto_apply()
        quant._compute_quantity_packaging()

        self.assertEqual(quant.packaging_name, self.packaging.name)
        self.assertAlmostEqual(quant.packaging_qty_available, 2.0, places=4)
        self.assertAlmostEqual(quant.volume_available, 36.0, places=4)
        self.assertAlmostEqual(quant.weight_available, 48.0, places=4)

    def test_04_account_move_line_liters(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': self.sale_journal.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'S2C Product Package Invoice Line',
                'product_id': self.product.id,
                'quantity': 5.0,
                'price_unit': 100.0,
                'account_id': self.income_account.id,
            })],
        })

        line = invoice.invoice_line_ids[:1]
        self.assertTrue(line, 'The invoice should contain one line')
        self.assertAlmostEqual(line.line_liters, 7.5, places=4)

    def test_05_packaging_quant_view_compute(self):
        self._create_done_move(12.0)

        packaging_quant = self.env['product.packaging.quant'].search([
            ('product_id', '=', self.product.id),
            ('location_id', '=', self.stock_location.id),
            ('product_packaging_id', '=', self.packaging.id),
        ], limit=1)
        self.assertTrue(packaging_quant, 'Expected at least one record in product.packaging.quant')

        packaging_quant._compute_quantity()
        self.assertAlmostEqual(packaging_quant.quantity, -12.0, places=4)
        self.assertAlmostEqual(packaging_quant.packaging_quantity, -1.0, places=4)
