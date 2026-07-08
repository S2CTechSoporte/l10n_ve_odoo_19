# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    city = fields.Char(related="partner_id.city", store=True, string="Ciudad")
    municipality_id = fields.Many2one('res.country.state.municipality', string="Municipio", related="partner_id.municipality_id", store=True)
    state_id = fields.Many2one('res.country.state', string="Estado", related="partner_id.state_id", store=True)
