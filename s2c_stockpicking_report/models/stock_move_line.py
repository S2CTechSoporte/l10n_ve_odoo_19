# -*- coding: utf-8 -*-

from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    city = fields.Char(related="picking_id.city", store=True, string="Ciudad")
    municipality_id = fields.Many2one(
        related="picking_id.municipality_id",
        comodel_name="res.country.state.municipality",
        store=True,
        string="Municipio",
    )
    state_id = fields.Many2one(
        related="picking_id.state_id",
        comodel_name="res.country.state",
        store=True,
        string="Estado",
    )