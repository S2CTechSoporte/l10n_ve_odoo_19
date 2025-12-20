# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fcurrency_id = fields.Many2one("res.currency", related="company_id.fcurrency_id", string="Moneda Dual Ref.", readonly=False)

