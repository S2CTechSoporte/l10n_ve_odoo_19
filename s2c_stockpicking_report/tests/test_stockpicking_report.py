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
            'city': 'Caracas',
            'state_id': cls.state_merida.id,
        })

        cls.product = cls.env['product.product'].create({
            'name': 'S2C Stock Picking Report Product',
            'type': 'consu',
            'is_storable': True,
            'uom_id': cls.uom_unit.id,
            'weight': 1.0,
            'volume': 1.0,
        })

        cls.packaging = cls.env['product.packaging'].create({
            'name': 'Pack x10',
            'product_id': cls.product.id,
            'product_uom_id': cls.uom_unit.id,
            'qty': 10.0,
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

    def _create_picking(self, with_lines=False, packages=None, origin='SO-001'):
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

        if with_lines:
            package_records = packages or [self.package_1]
            total_quantity = self.packaging.qty * len(package_records)
            move = self.env['stock.move'].create({
                'picking_id': picking.id,
                'product_id': self.product.id,
                'product_uom': self.uom_unit.id,
                'product_uom_qty': total_quantity,
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'product_packaging_id': self.packaging.id,
                'description_picking': 'Stock picking report move',
            })

            for package in package_records:
                self.env['stock.move.line'].create({
                    'picking_id': picking.id,
                    'move_id': move.id,
                    'product_id': self.product.id,
                    'product_uom_id': self.uom_unit.id,
                    'quantity': self.packaging.qty,
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

    def test_03_batch_grouped_data_report_and_validation(self):
        picking = self._create_picking(with_lines=True, packages=[self.package_1])
        batch = self.env['stock.picking.batch'].create({
            'picking_type_id': self.picking_type_out.id,
            'picking_ids': [(6, 0, [picking.id])],
        })

        grouped_data = batch._get_grouped_data()
        self.assertTrue(grouped_data, 'Grouped data should not be empty for a batch with move lines')
        self.assertAlmostEqual(grouped_data[0]['qty'], 1.0, places=4)
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

    def test_04_stock_picking_reports_render_in_odoo_19(self):
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
