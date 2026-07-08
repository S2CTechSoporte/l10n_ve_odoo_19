# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    product_packaging_id = fields.Many2one(
        'product.packaging',
        string='Empaquetado',
        domain="[('product_id', '=', product_id)]",
        copy=False,
    )

    packaging_quantity = fields.Float('Cantidad de Empaque', compute="_compute_packaging_quantity", inverse="_inverse_packaging_quantity", store=True,precompute=True)

    @api.depends('product_uom_qty', 'product_packaging_id.qty')
    def _compute_packaging_quantity(self):
        for record in self:
            record.packaging_quantity = record.product_uom_qty
            if record.product_packaging_id:
                qty  = record.product_packaging_id.qty if record.product_packaging_id.qty > 0 else 1
                record.packaging_quantity = record.product_uom_qty / qty


    def _inverse_packaging_quantity(self):
         for record in self:
            record.product_uom_qty = record.packaging_quantity
            if record.product_packaging_id:
                qty  = record.product_packaging_id.qty if record.product_packaging_id.qty > 0 else 1
                record.product_uom_qty = record.packaging_quantity * qty
    
            
            

                


        


