# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from datetime import date


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    company_fcurrency_id = fields.Many2one(
        comodel_name='res.currency',
        string="Company Currency",
        related='company_id.fcurrency_id')

    # ==== Amount fields ====
    amount_fcurrency = fields.Monetary(
        currency_field='company_fcurrency_id',
        compute='_compute_amount_fcurrency',
        store=True,
        default=0.0,
        )
    
    @api.depends('credit_move_id.balance_fcurrency', 'debit_move_id.balance_fcurrency')
    def _compute_amount_fcurrency(self):
        # debit  --> factura
        # credit --> pago 
        for record in self:
            payment_move = self.env['account.move.line']
            if record.credit_move_id.move_id.move_type in ('out_invoice', 'in_invoice') and record.debit_move_id.move_id.move_type not in ('out_invoice', 'in_invoice'):
                payment_move = record.debit_move_id
            elif record.debit_move_id.move_id.move_type in ('out_invoice', 'in_invoice') and record.credit_move_id.move_id.move_type not in ('out_invoice', 'in_invoice'):
                payment_move = record.credit_move_id
            # else:
            #     raise UserError(_("The partial reconcile record is not valid."))
            
            record.amount_fcurrency = abs(payment_move.balance_fcurrency)
