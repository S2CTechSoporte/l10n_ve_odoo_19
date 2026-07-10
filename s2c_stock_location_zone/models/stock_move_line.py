# -*- coding: utf-8 -*-

from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    city = fields.Char(related='picking_id.city', store=True, string='Ciudad')
    municipality_id = fields.Many2one(
        'res.country.state.municipality',
        related='picking_id.municipality_id',
        store=True,
        string='Municipio',
    )
    state_id = fields.Many2one(
        'res.country.state',
        related='picking_id.state_id',
        store=True,
        string='Estado',
    )