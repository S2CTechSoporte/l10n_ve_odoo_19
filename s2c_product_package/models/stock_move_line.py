# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    product_packaging_id = fields.Many2one(string="Empaquetado", related='move_id.product_packaging_id', store=True)
    packaging_quantity = fields.Float('Cantidad de Empaque', compute="_compute_packaging_quantity", inverse="_inverse_packaging_quantity", store=True,precompute=False)

    @api.depends('quantity', 'product_packaging_id.qty')
    def _compute_packaging_quantity(self):
        for record in self:
            record.packaging_quantity = record.quantity
            if record.product_packaging_id:
                qty  = record.product_packaging_id.qty if record.product_packaging_id.qty > 0 else 1
                record.packaging_quantity = record.quantity / qty
    

    def _inverse_packaging_quantity(self):
        for record in self:
            record.quantity = record.packaging_quantity
            if record.product_packaging_id:
                qty  = record.product_packaging_id.qty if record.product_packaging_id.qty > 0 else 1
                record.quantity = record.packaging_quantity * qty


            
            

                


        


