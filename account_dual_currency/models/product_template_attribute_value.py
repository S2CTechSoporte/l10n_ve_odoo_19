# -*- coding: utf-8 -*-

from itertools import groupby
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import AccessError, UserError, ValidationError

class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    fcurrency_id = fields.Many2one('res.currency', string='Currency USD', default=lambda self: self.env.user.company_id.fcurrency_id.id)

    price_extra_fcurrency = fields.Monetary(string='Precio Extra $', currency_field='fcurrency_id')

    @api.onchange('price_extra_fcurrency')
    def _onchange_price_extra_fcurrency(self):
        self.price_extra = self.price_extra_fcurrency * self.fcurrency_id.inverse_rate