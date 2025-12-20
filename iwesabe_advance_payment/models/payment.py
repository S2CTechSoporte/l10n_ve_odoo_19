# -*- coding: utf-8 -*-

from datetime import date
from odoo import models, fields, api, _

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_advance_payment = fields.Boolean(copy=False)

    def action_post(self):
        result = super().action_post()
        for record in self:
            if record.is_advance_payment:
                if 'ADV/PYMT/' not in record.name:
                    new_name = 'ADV/PYMT/'+record.name
                    record.name = new_name
        return result
    
    