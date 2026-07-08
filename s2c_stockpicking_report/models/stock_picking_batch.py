# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from markupsafe import Markup


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    total_weight = fields.Float(string='Total Weight')
    sale_orders = fields.Char(string='Sale Orders')
    total_orders = fields.Integer(string='Total Orders')

    def _get_grouped_data(self):
        self.ensure_one()
        data = []
        row = {}
        for move_line in self.picking_ids.mapped('move_line_ids').sorted(key=lambda line: (line.location_id.complete_name, line.product_id.id)):
            key = (move_line.location_id.id,
            move_line.product_id.id,
            move_line.lot_id.id,
            move_line.product_packaging_id.id)
            qty = move_line.packaging_quantity or move_line.quantity
            
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
                        'packaging': move_line.product_packaging_id.name or move_line.product_id.uom_name ,
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