# -*- coding: utf-8 -*-
from odoo import fields, models, tools, api
import datetime

class StockValuationLayer(models.Model):
    _inherit = 'stock.move'

    fcurrency_id = fields.Many2one("res.currency",
                                     string="Divisa de Referencia",
                                     default=lambda self: self.env.company.fcurrency_id )
    unit_cost_fcurrency = fields.Monetary('Valor unitario ¤', default=0.0,currency_field='fcurrency_id', compute='_compute_all_values_fcurrency', store=True)
    value_fcurrency = fields.Monetary('Valor Total ¤', default=0.0,currency_field='fcurrency_id', compute='_compute_all_values_fcurrency', store=True)

    remaining_value_fcurrency = fields.Monetary('Valor Restante ¤', default=0.0,currency_field='fcurrency_id', compute='_compute_all_values_fcurrency', store=True)

    tasa = fields.Float('Tasa de Referencia',  digits='Dual_Currency_rate', compute='_compute_all_values_fcurrency', store=True)

    @api.depends('price_unit', 'value', 'remaining_value', 'fcurrency_id', 'company_id')
    def _compute_all_values_fcurrency(self):
        for layer in self:
            company_currency = layer.company_id.currency_id
            date = fields.Date.context_today(layer)
            layer.unit_cost_fcurrency = company_currency._convert(layer.price_unit, layer.fcurrency_id, layer.company_id, date)
            layer.value_fcurrency = company_currency._convert(layer.value, layer.fcurrency_id, layer.company_id, date)
            layer.remaining_value_fcurrency = company_currency._convert(layer.remaining_value, layer.fcurrency_id, layer.company_id, date)
            layer.tasa = company_currency._convert(1, layer.fcurrency_id, layer.company_id, date)