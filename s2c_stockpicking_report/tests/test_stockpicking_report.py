# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestS2CStockPickingReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')

        cls.picking_type_out = cls.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('company_id', '=', cls.env.company.id),
        ], limit=1)
        cls.assertTrue(cls.picking_type_out, 'An outgoing picking type is required for stock picking report tests')

        country = cls.env['res.country'].search([('code', '=', 'VE')], limit=1)
        if not country:
            country = cls.env.ref('base.us')

        cls.state_merida = cls.env['res.country.state'].search([
            ('country_id', '=', country.id),
            ('code', '=', 'ME'),
        ], limit=1)
        if not cls.state_merida:
            cls.state_merida = cls.env['res.country.state'].create({
                'name': 'Merida',
                'code': 'ME',
                'country_id': country.id,
            })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Compañía Ñandú',
            'customer_rank': 1,
            'company_type': 'person',
            'country_id': country.id,
            'city': 'Caracas',
            'state_id': cls.state_merida.id,
        })

        municipality_model = cls.env['res.country.state.municipality']
        cls.municipality = municipality_model.search([
            ('state_id', '=', cls.state_merida.id),
            ('name', '=', 'Libertador'),
        ], limit=1)
        if not cls.municipality:
            cls.municipality = municipality_model.create({
                'state_id': cls.state_merida.id,
                'name': 'Libertador',
                'code': 'LIB',
            })
        cls.partner.municipality_id = cls.municipality

        cls.pricelist = cls.env['product.pricelist'].search([
            ('currency_id', '=', cls.env.company.currency_id.id),
        ], limit=1)
        cls.assertTrue(cls.pricelist, 'A sales pricelist is required for stock picking report tests')

        cls.product = cls.env['product.product'].create({
            'name': 'S2C Stock Picking Report Product',
            'type': 'consu',
            'is_storable': True,
            'uom_id': cls.uom_unit.id,
            'weight': 1.0,
            'volume': 1.0,
            'list_price': 25.0,
        })

        cls.package_1 = cls.env['stock.package'].create({'name': '1'})
        cls.package_2 = cls.env['stock.package'].create({'name': '2'})

    def _extract_report_name(self, action):
        report_name = action.get('report_name')
        if report_name:
            return report_name
        return (action.get('context') or {}).get('report_action', {}).get('report_name')

    def _render_report_html(self, xmlid, records):
        report = self.env.ref(xmlid)
        html, _report_type = self.env['ir.actions.report']._render_qweb_html(
            report.report_name,
            records.ids,
        )
        return html.decode() if isinstance(html, bytes) else html

    def _create_sale_order(self, client_order_ref='INS-001', origin=False, price_unit=25.0):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'pricelist_id': self.pricelist.id,
            'client_order_ref': client_order_ref,
            'origin': origin,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2.0,
                'price_unit': price_unit,
                'name': self.product.name,
            })],
        })

    def _create_picking(self, with_lines=False, packages=None, origin='SO-001', sale_order=False):
        if sale_order and origin == 'SO-001':
            origin = sale_order.name

        picking = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'origin': origin,
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'name_driver': 'JUAN PEREZ',
            'identification_driver': 'V-12345678',
            'vehicle': 'CAMION S2C',
            'license_plate': 'AB123CD',
            'vehicle_brand': 'S2C',
            'vehicle_type': 'Cargo',
        })

        if sale_order and 'sale_id' in picking._fields:
            picking.sale_id = sale_order

        if with_lines:
            package_records = packages or [self.package_1]
            total_quantity = 10.0 * len(package_records)
            move = self.env['stock.move'].create({
                'picking_id': picking.id,
                'product_id': self.product.id,
                'sale_line_id': sale_order.order_line[:1].id if sale_order and sale_order.order_line else False,
                'product_uom': self.uom_unit.id,
                'product_uom_qty': total_quantity,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'description_picking': 'Stock picking report move',
            })

            for package in package_records:
                self.env['stock.move.line'].create({
                    'picking_id': picking.id,
                    'move_id': move.id,
                    'product_id': self.product.id,
                    'product_uom_id': self.uom_unit.id,
                    'quantity': 10.0,
                    'location_id': self.stock_location.id,
                    'location_dest_id': self.customer_location.id,
                    'result_package_id': package.id,
                })

        return picking

    def test_01_action_print_label_bags_validation_and_success(self):
        empty_picking = self._create_picking(with_lines=False)
        with self.assertRaises(UserError):
            empty_picking.action_print_label_bags()

        picking = self._create_picking(with_lines=True)
        action = picking.action_print_label_bags()
        self.assertEqual(self._extract_report_name(action), 's2c_stockpicking_report.report_pickinglabel')

    def test_02_total_destination_packages_and_raw_helpers(self):
        picking = self._create_picking(
            with_lines=True,
            packages=[self.package_1, self.package_2],
            origin='SO/Ñ-001',
        )
        expected_vat = self.env.company.vat or ''

        self.assertEqual(picking.total_destination_packages, 2)
        self.assertEqual(str(picking.company_vat_raw()), expected_vat)
        self.assertEqual(str(picking.origin_raw()), 'SO/Ñ-001')
        self.assertEqual(str(picking.state_name_raw()), 'MERIDA')
        self.assertEqual(str(picking.partner_name_raw()), 'COMPANIA NANDU')
        self.assertEqual(picking.packages_count, 2)
        self.assertAlmostEqual(picking.shipping_weight, 20.0, places=4)

    def test_03_transport_relation_dataset_views_and_report(self):
        sale_order = self._create_sale_order(origin='998877', price_unit=25.0)
        picking = self._create_picking(
            with_lines=True,
            packages=[self.package_1, self.package_2],
            sale_order=sale_order,
        )
        batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.picking_type_out.id,
            'picking_ids': [(6, 0, [picking.id])],
        })

        first_move_line = picking.move_line_ids[:1]
        self.assertEqual(first_move_line.city, 'Caracas')
        self.assertEqual(first_move_line.state_id, self.state_merida)
        self.assertEqual(first_move_line.municipality_id, self.municipality)

        lines = batch._get_transport_relation_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['guia'], picking.name)
        self.assertEqual(lines[0]['pedido'], sale_order.name)
        self.assertEqual(lines[0]['solicitud'], '998877')
        self.assertEqual(lines[0]['cliente'], self.partner.name)
        self.assertEqual(lines[0]['destino'], 'Merida / Caracas / Libertador')
        self.assertEqual(lines[0]['bultos'], 2)
        self.assertAlmostEqual(lines[0]['peso'], picking.shipping_weight, places=4)
        self.assertAlmostEqual(lines[0]['monto'], sale_order.amount_total, places=4)

        totals = batch._get_transport_relation_totals()
        self.assertEqual(totals['total_orders'], 1)
        self.assertEqual(totals['total_packages'], 2)
        self.assertAlmostEqual(totals['total_weight'], 20.0, places=4)
        self.assertAlmostEqual(totals['total_amount'], sale_order.amount_total, places=4)

        action = batch.action_print_transport_relation()
        self.assertEqual(self._extract_report_name(action), 's2c_stockpicking_report.report_transport_relation_document')

        report_html = self._render_report_html('s2c_stockpicking_report.action_report_transport_relation', batch)
        self.assertIn('RELACION DE TRANSPORTE', report_html)
        self.assertIn(picking.name, report_html)
        self.assertIn(sale_order.name, report_html)
        self.assertIn('998877', report_html)

        empty_batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.picking_type_out.id,
        })
        with self.assertRaises(UserError):
            empty_batch.action_print_transport_relation()

    def test_04_batch_grouped_data_report_and_validation(self):
        picking = self._create_picking(with_lines=True, packages=[self.package_1])
        batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.picking_type_out.id,
            'picking_ids': [(6, 0, [picking.id])],
        })

        grouped_data = batch._get_grouped_data()
        self.assertTrue(grouped_data, 'Grouped data should not be empty for a batch with move lines')
        self.assertAlmostEqual(grouped_data[0]['qty'], 10.0, places=4)
        self.assertEqual(batch.total_orders, 1)
        self.assertEqual(str(batch.company_vat_raw()), self.env.company.vat or '')

        action = batch.action_print_batch_label_bags()
        self.assertEqual(self._extract_report_name(action), 's2c_stockpicking_report.report_pickingbatch_label')

        report_parser = self.env['report.stock_picking_batch.report_picking_batch']
        values = report_parser._get_report_values(batch.ids)
        self.assertEqual(values['doc_model'], 'stock.picking.batch')
        self.assertTrue(values['datas'])
        self.assertEqual(values['total_orders'], 1)

        empty_batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.picking_type_out.id,
        })
        with self.assertRaises(UserError):
            empty_batch.action_print_batch_label_bags()

    def test_05_stock_picking_reports_render_in_odoo_19(self):
        picking = self._create_picking(with_lines=True, packages=[self.package_1], origin='SO-REPORT-001')

        picking_operations_html = self._render_report_html('stock.action_report_picking', picking)
        delivery_slip_html = self._render_report_html('stock.action_report_delivery', picking)
        custom_delivery_slip_html = self._render_report_html(
            's2c_stockpicking_report.action_report_custom_deliveryslip',
            picking,
        )

        self.assertIn('LISTA DE PICKING', picking_operations_html)
        self.assertIn(picking.name, picking_operations_html)
        self.assertIn('LISTA DE PICKING', delivery_slip_html)
        self.assertIn(picking.name, delivery_slip_html)
        self.assertIn('Traslado Nro:', custom_delivery_slip_html)
        self.assertIn(picking.name, custom_delivery_slip_html)
