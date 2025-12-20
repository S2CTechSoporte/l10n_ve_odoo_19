# -*- coding: utf-8 -*-
from odoo import fields, models, tools, api, _
from collections import defaultdict
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero


class AdjustmentLines(models.Model):
    _inherit = 'stock.valuation.adjustment.lines'

    tax_today = fields.Float(string="Tasa", compute='_compute_final_cost_fcurrency', store=True)
    fcurrency_id = fields.Many2one(related="cost_id.company_id.fcurrency_id")

    former_cost_fcurrency = fields.Monetary(currency_field='fcurrency_id', string='Valor Original ¤', compute='_compute_final_cost_fcurrency', store=True)
    additional_landed_cost_fcurrency = fields.Monetary(currency_field='fcurrency_id',string='Costo adicionales ¤', compute='_compute_final_cost_fcurrency', store=True)
    final_cost_fcurrency = fields.Monetary(currency_field='fcurrency_id', string='Nuevo Valor ¤', compute='_compute_final_cost_fcurrency', store=True)

    @api.depends('former_cost', 'additional_landed_cost', 'final_cost_fcurrency')
    def _compute_final_cost_fcurrency(self):
        for line in self:
            line.former_cost_fcurrency = line.cost_id.company_id.currency_id._convert(line.former_cost, line.fcurrency_id, line.cost_id.company_id, fields.Date.today())
            line.additional_landed_cost_fcurrency = line.cost_id.company_id.currency_id._convert(line.additional_landed_cost, line.fcurrency_id, line.cost_id.company_id, fields.Date.today())
            line.final_cost_fcurrency = line.cost_id.company_id.currency_id._convert(line.final_cost, line.fcurrency_id, line.cost_id.company_id, fields.Date.today())
            line.tax_today = line.cost_id.company_id.currency_id._convert(1, line.fcurrency_id, line.cost_id.company_id, fields.Date.today())


    