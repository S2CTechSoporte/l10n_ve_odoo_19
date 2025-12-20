
# -*- coding: UTF-8 -*-
from email.policy import default

from odoo import fields, models, api
from odoo.exceptions import UserError
import re

class ResPartner(models.Model):
    _inherit = 'res.partner'

    credit_limit_currency = fields.Many2one("res.currency",
                                      string="Moneda",
                                      help="Moneda del Límite de crédito",
                                      default=lambda self: self.env.ref('base.USD').id
                                      )
                                     