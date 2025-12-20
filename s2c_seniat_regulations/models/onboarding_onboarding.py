# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.addons.onboarding.models.onboarding_progress import ONBOARDING_PROGRESS_STATES


class Onboarding(models.Model):
    _inherit = 'onboarding.onboarding'

    def _prepare_rendering_values(self):
        values = super(Onboarding, self)._prepare_rendering_values()
        values.update({
            'orders_without_invoice': self.env['sale.order']._compute_orders_without_invoice()
        })
        return values