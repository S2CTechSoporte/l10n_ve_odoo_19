# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProductPackaging(models.Model):
    _name = 'product.packaging'
    _description = 'Product Packaging'

    name = fields.Char(string='Name', required=True)
    product_id = fields.Many2one('product.product', string='Product', required=True, ondelete='cascade')
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True,
        readonly=True,
    )
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    qty = fields.Float(string='Contained Quantity', required=True, default=1.0)

    packaging_liters = fields.Float("Litros por empaquetado", compute="_compute_packaging_liters", store=True, digits=(12,4))
    packaging_weight = fields.Float("Peso por empaquetado", compute="_compute_packaging_weight", store=True, digits=(12,4))

    _sql_constraints = [
        ('s2c_product_packaging_qty_positive', 'CHECK(qty > 0)', 'Packaging quantity must be greater than zero.'),
    ]

    @api.depends('qty', 'product_id.product_tmpl_id.volume')
    def _compute_packaging_liters(self):
        for packaging in self:
            volume = packaging.product_id.product_tmpl_id.volume if packaging.product_id else 0.0
            packaging.packaging_liters = packaging.qty * volume
        
    @api.depends('qty', 'product_id.product_tmpl_id.weight')
    def _compute_packaging_weight(self):
        for packaging in self:
            weight = packaging.product_id.product_tmpl_id.weight if packaging.product_id else 0.0
            packaging.packaging_weight = packaging.qty * weight