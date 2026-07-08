# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    packaging_ids = fields.One2many('product.packaging', 'product_id', string='S2C Packagings')

    packaging_qty_available = fields.Float(string='Cantidad empaquetado disponible', compute='_compute_quantity_packaging', store=True)
    packaging_name = fields.Char(string='Empaquetado', compute='_compute_quantity_packaging', store=True)
    packaging_free_qty = fields.Float(string='Cantidad empaquetado Libre de Usar', compute='_compute_quantity_packaging', store=True)
    volume_available = fields.Float(string='Litros disponibles', digits="Picking List Volume", compute='_compute_quantity_packaging', store=True)
    weight_available = fields.Float(string='Peso disponible', digits="Picking List Weight", compute='_compute_quantity_packaging', store=True)
    


    @api.depends('free_qty', 'qty_available', 'packaging_ids.qty', 'packaging_ids.name', 'volume', 'weight')
    def _compute_quantity_packaging(self):
        for record in self:
            packaging = record.packaging_ids[:1]
            qty = packaging.qty if packaging and packaging.qty > 0 else 1
            name = packaging.name if packaging else ''
            
            record.packaging_name = name
            record.packaging_qty_available = record.qty_available / qty
            record.packaging_free_qty = record.free_qty / qty
            record.volume_available =  record.qty_available * record.volume
            record.weight_available = record.qty_available * record.weight


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    packaging_ids = fields.One2many('product.packaging', 'product_tmpl_id', string='S2C Packagings')




