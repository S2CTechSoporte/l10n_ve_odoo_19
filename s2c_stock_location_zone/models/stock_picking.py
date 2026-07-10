# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    city = fields.Char(related='partner_id.city', store=True, string='Ciudad')
    municipality_id = fields.Many2one(
        'res.country.state.municipality',
        related='partner_id.municipality_id',
        store=True,
        string='Municipio',
    )
    state_id = fields.Many2one(
        'res.country.state',
        related='partner_id.state_id',
        store=True,
        string='Estado',
    )