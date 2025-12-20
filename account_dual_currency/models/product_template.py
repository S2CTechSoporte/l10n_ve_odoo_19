# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class Productos(models.Model):
    _inherit = 'product.template'

    list_price_fcurrency = fields.Float(string="Precio de venta ¤",compute="_compute_list_price_fcurrency", store=True)
    standard_price_fcurrency = fields.Float(string="Costo ¤", compute='_compute_standard_price_fcurrency', store=True)
    costo_reposicion_fcurrency = fields.Float(string="Costo Reposición ¤")

    @api.depends('list_price')
    def _compute_list_price_fcurrency(self):
        currency_id = self.env.company.currency_id 
        fcurrency_id = self.env.company.fcurrency_id
        for record in self:
            record.list_price_fcurrency = currency_id._convert(record.list_price, fcurrency_id)
    
    @api.depends('standard_price')
    def _compute_standard_price_fcurrency(self):
        currency_id = self.env.company.currency_id
        fcurrency_id = self.env.company.fcurrency_id
        for record in self:
            record.standard_price_fcurrency = currency_id._convert(record.standard_price, fcurrency_id)

    
    # def _set_standard_price_fcurrency(self):
    #     for template in self:
    #         if len(template.product_variant_ids) == 1:
    #             template.product_variant_ids.standard_price_fcurrency = template.standard_price_fcurrency

    # @api.depends_context('company')
    # @api.depends('product_variant_ids', 'product_variant_ids.standard_price_fcurrency')
    # def _compute_standard_price_fcurrency(self):
    #     # Depends on force_company context because standard_price is company_dependent
    #     # on the product_product
    #     for rec in self:
    #         if len(rec.product_variant_ids) == 1:
    #             rec.standard_price_fcurrency = rec.product_variant_ids[0].standard_price_fcurrency
    #         else:
    #             rec.standard_price_fcurrency = 0.0

    # @api.onchange('list_price_fcurrency')
    # def _onchange_list_price_fcurrency(self):
    #     for rec in self:
    #         if rec.list_price_fcurrency:
    #             if rec.list_price_fcurrency >0:
    #                 tasa = self.env.company.fcurrency_id
    #                 if tasa:
    #                     rec.list_price = rec.list_price_fcurrency * tasa.inverse_rate

    # @api.onchange('standard_price_fcurrency')
    # def _onchange_standard_price_fcurrency(self):
    #     for rec in self:
    #         if len(rec.product_variant_ids) == 1:
    #             rec.product_variant_ids[0].standard_price_fcurrency = rec.standard_price_fcurrency

    #         if rec.standard_price_fcurrency and rec.categ_id.property_valuation == 'manual_periodic':
    #             if rec.standard_price_fcurrency > 0:
    #                 tasa = self.env.company.fcurrency_id
    #                 if tasa:
    #                     rec.standard_price = rec.standard_price_fcurrency * tasa.inverse_rate


