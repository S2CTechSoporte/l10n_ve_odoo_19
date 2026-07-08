# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    packaging_name = fields.Char(string='Empaquetado', compute='_compute_quantity_packaging', store=True)
    packaging_qty_available = fields.Float(string='Cantidad empaquetado disponible', compute='_compute_quantity_packaging', store=True)
    packaging_reserved_qty = fields.Float(string='Cantidad empaquetado reservada', compute='_compute_quantity_packaging', store=True)
    volume_available = fields.Float(string='Litros disponibles', digits="Picking List Volume", compute='_compute_quantity_packaging', store=True)
    weight_available = fields.Float(string='Peso disponible', digits="Picking List Weight", compute='_compute_quantity_packaging', store=True)
    
    @api.depends(
        'inventory_quantity_auto_apply',
        'reserved_quantity',
        'product_tmpl_id.packaging_ids.qty',
        'product_tmpl_id.packaging_ids.name',
        'product_tmpl_id.volume',
        'product_tmpl_id.weight',
    )
    def _compute_quantity_packaging(self):
        for record in self:
            packaging = record.product_tmpl_id.packaging_ids[:1]
            qty = packaging.qty if packaging and packaging.qty > 0 else 1
            name = packaging.name if packaging else ''
            
            record.packaging_name = name
            record.packaging_qty_available = record.inventory_quantity_auto_apply / qty
            record.packaging_reserved_qty = record.reserved_quantity / qty
            record.volume_available =  record.inventory_quantity_auto_apply * record.product_tmpl_id.volume
            record.weight_available = record.inventory_quantity_auto_apply * record.product_tmpl_id.weight

