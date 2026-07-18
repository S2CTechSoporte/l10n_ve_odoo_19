# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from markupsafe import Markup


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    total_weight = fields.Float(string='Total Weight')
    sale_orders = fields.Char(string='Sale Orders')
    total_orders = fields.Integer(string='Total Orders')

    def _get_transport_relation_sale_order(self, picking):
        self.ensure_one()
        if 'sale_id' in picking._fields and picking.sale_id:
            return picking.sale_id
        if 'reference_ids' in picking._fields and picking.reference_ids.sale_ids:
            return picking.reference_ids.sale_ids[:1]
        return self.env['sale.order']

    def _get_transport_relation_order_name(self, picking):
        self.ensure_one()
        sale_order = self._get_transport_relation_sale_order(picking)
        if sale_order:
            return sale_order.name or picking.origin or picking.name
        return picking.origin or picking.name

    def _get_transport_relation_request(self, picking):
        self.ensure_one()
        sale_order = self._get_transport_relation_sale_order(picking)
        if sale_order:
            return sale_order.origin or ''
        return ''

    def _get_transport_relation_amount(self, picking):
        self.ensure_one()
        sale_order = self._get_transport_relation_sale_order(picking)
        return sale_order.amount_total if sale_order else 0.0

    def _get_transport_relation_destination(self, picking):
        self.ensure_one()
        partner = picking.partner_id
        destination_parts = [
            (partner.state_id.name if partner else picking.state_id.name) or '',
            (partner.city if partner else picking.city) or '',
            (partner.municipality_id.name if partner else picking.municipality_id.name) or '',
        ]
        return ' / '.join(part for part in destination_parts if part)

    def _get_transport_relation_lines(self):
        self.ensure_one()
        lines = []
        sorted_pickings = self.picking_ids.sorted(
            key=lambda picking: (
                self._get_transport_relation_order_name(picking) or '',
                picking.name or '',
                picking.id,
            )
        )

        for item, picking in enumerate(sorted_pickings, start=1):
            lines.append({
                'item': item,
                'guia': picking.name,
                'pedido': self._get_transport_relation_order_name(picking),
                'solicitud': self._get_transport_relation_request(picking),
                'cliente': picking.partner_id.name or '',
                'destino': self._get_transport_relation_destination(picking),
                'peso': picking.shipping_weight,
                'bultos': picking.packages_count,
                'monto': self._get_transport_relation_amount(picking),
                'transferencia': picking.name,
            })

        return lines

    def _get_transport_relation_totals(self):
        self.ensure_one()
        lines = self._get_transport_relation_lines()
        order_names = {line['pedido'] for line in lines if line['pedido']}
        return {
            'total_orders': len(order_names) if order_names else len(lines),
            'total_weight': sum(line['peso'] for line in lines),
            'total_packages': sum(line['bultos'] for line in lines),
            'total_amount': sum(line['monto'] for line in lines),
        }

    def _get_transport_relation_pages(self, page_size=18):
        self.ensure_one()
        lines = self._get_transport_relation_lines()
        return [lines[index:index + page_size] for index in range(0, len(lines), page_size)] or [[]]

    def _get_grouped_data(self):
        self.ensure_one()
        data = []
        row = {}
        for move_line in self.picking_ids.mapped('move_line_ids').sorted(key=lambda line: (line.location_id.complete_name, line.product_id.id)):
            key = (move_line.location_id.id,
            move_line.product_id.id,
            move_line.lot_id.id)
            qty = move_line.quantity
            
            if  key in row:
                row[key].update({
                    'qty': row[key]['qty'] + qty
                })
            else:
                row.update( {
                    key: {
                        'location': move_line.location_id.display_name,
                        'product': move_line.product_id.name,
                        'default_code': move_line.product_id.default_code,
                        'product_name': move_line.product_id.product_tmpl_id.name,
                        'lot': move_line.lot_id.name or ' ',
                        'packaging': move_line.product_uom_id.name,
                        'qty': qty
                    }
                })
        
        picking_model = self.env['stock.picking']
        if 'sale_id' in picking_model._fields:
            order_names = [name for name in self.picking_ids.mapped('sale_id.name') if name]
        else:
            order_names = [origin for origin in self.picking_ids.mapped('origin') if origin]

        self.sale_orders = ', '.join(order_names)
        self.total_weight = sum([move_line.product_id.product_tmpl_id.weight * move_line.quantity for move_line in self.picking_ids.mapped('move_line_ids')])
        self.total_orders = len(self.picking_ids)
        
        for key, value in row.items():
            data.append(value)

           
        return data

    def action_print_batch_label_bags(self):
        self.ensure_one()
        if not self.move_line_ids:
            raise UserError("No hay líneas de movimiento en este picking batch.")

        return self.env.ref('s2c_stockpicking_report.action_print_batch_label_bags_label').report_action(self)

    def action_print_transport_relation(self):
        self.ensure_one()
        if not self.picking_ids:
            raise UserError("No hay traslados en este picking batch.")

        return self.env.ref('s2c_stockpicking_report.action_report_transport_relation').report_action(self)

    def company_vat_raw(self):
        return Markup(self.company_id.vat or '')


class PickingBatchReport(models.AbstractModel):
    _name = 'report.stock_picking_batch.report_picking_batch'
    _description = 'Stock Picking Batch Report'
    # reporte standard asociado a un action
    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.picking.batch'].browse(docids)
        batch = docs[:1]

        return {
            'doc_ids': docids,
            'doc_model': 'stock.picking.batch',
            'docs': docs,
            'datas': batch._get_grouped_data() if batch else [],
            'total_weight': batch.total_weight or 0,
            'total_orders': batch.total_orders or 0,
        }        