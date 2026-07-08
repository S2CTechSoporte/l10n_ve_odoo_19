# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductPackagingQuant(models.Model):

    _name = 'product.packaging.quant'
    _description = 'Existencia por Empaque'
    _auto = False

    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañia', readonly=True)
    location_id = fields.Many2one('stock.location', string="Ubicación", readonly=True)
    # lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number', readonly=True)
    product_packaging_id = fields.Many2one('product.packaging', string='Empaque', readonly=True)

    quantity = fields.Float(string="Cantidad", digits='Product Unit of Measure', compute="_compute_quantity")
    packaging_quantity = fields.Float(string="Cant. Empaque", digits='Product Unit of Measure', compute="_compute_quantity")

    @api.depends('product_id','location_id','product_packaging_id')
    def _compute_quantity(self):
        for record in self:
            # desde
            move_lines = self.env['stock.move.line'].search([
                    ('company_id', '=', record.company_id.id),
                    ('product_id', '=', record.product_id.id),
                    ('location_id', '=', record.location_id.id),
                    ('product_packaging_id','=',record.product_packaging_id.id),
                    ('move_id.state', '=', 'done')
                ])
            
            from_quantity = 0
            for line in move_lines:
                from_quantity += line.quantity 

            move_lines = self.env['stock.move.line'].search([
                    ('company_id', '=', record.company_id.id),
                    ('product_id', '=', record.product_id.id),
                    ('location_dest_id', '=', record.location_id.id),
                    ('product_packaging_id','=',record.product_packaging_id.id),
                    ('move_id.state', '=', 'done')
                ])
            to_quantity = 0
            for line in move_lines:
                to_quantity += line.quantity
            
            record.quantity = to_quantity - from_quantity
            record.packaging_quantity = record.quantity / (record.product_packaging_id.qty if record.product_packaging_id.qty > 0 else 1)
            
    @property
    def _table_query(self):
        return """
            select  min(id) as id, product_id, company_id, location_id, product_packaging_id  
            from stock_move_line sml 
            where state = 'done'
            group by  product_id, company_id, location_id, product_packaging_id
            order by location_id
        """