# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    line_liters = fields.Float(string="Litros del Renglon", compute="_compute_line_liters", store=True)

    @api.depends('quantity', 'product_id.product_tmpl_id.volume')
    def _compute_line_liters(self):
        for record in self:
            volume = record.product_id.product_tmpl_id.volume if record.product_id else 0.0
            record.line_liters = round(record.quantity * volume, 4)


