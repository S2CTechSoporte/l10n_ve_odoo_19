# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestS2CStockLocationZone(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.picking_type = cls.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        if not cls.picking_type:
            raise AssertionError('An outgoing picking type is required for zone tests')
        cls.state = cls.env['res.country.state'].create({
            'name': 'Merida',
            'code': 'ME-S2C',
            'country_id': cls.env.ref('base.ve').id,
        })
        cls.municipality = cls.env['res.country.state.municipality'].create({
            'name': 'Libertador',
            'code': 'LIB-S2C',
            'state_id': cls.state.id,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'S2C Zone Test Partner',
            'city': 'Caracas',
            'state_id': cls.state.id,
            'municipality_id': cls.municipality.id,
        })

    def test_picking_and_move_line_zone_fields(self):
        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type.id,
            'location_id': self.picking_type.default_location_src_id.id,
            'location_dest_id': self.picking_type.default_location_dest_id.id,
        })
        move_line = self.env['stock.move.line'].create({
            'picking_id': picking.id,
            'product_id': self.env.ref('product.product_product_4').id,
            'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            'location_id': picking.location_id.id,
            'location_dest_id': picking.location_dest_id.id,
        })
        self.assertEqual(picking.city, 'Caracas')
        self.assertEqual(picking.state_id, self.state)
        self.assertEqual(picking.municipality_id, self.municipality)
        self.assertEqual(move_line.city, 'Caracas')
        self.assertEqual(move_line.state_id, self.state)
        self.assertEqual(move_line.municipality_id, self.municipality)

    def test_zone_search_views_include_filters_and_groups(self):
        picking_search = self.env.ref('s2c_stock_location_zone.view_picking_search_inherit').arch_db
        move_line_search = self.env.ref('s2c_stock_location_zone.view_stock_move_line_search_inherit').arch_db
        for field_name in ('state_id', 'city', 'municipality_id'):
            self.assertIn("group_by': '%s'" % field_name, picking_search)
            self.assertIn("group_by': '%s'" % field_name, move_line_search)