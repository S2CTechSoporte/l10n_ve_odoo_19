# coding: utf-8
from odoo import models, fields, api
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    
    @api.depends('company_id', 'partner_id', 'amount_total')
    def _compute_partner_credit_warning(self):
        for order in self:
            order.with_company(order.company_id)
            order.partner_credit_warning = ''
            show_warning = order.state in ('draft', 'sent') and \
                           order.company_id.account_use_credit_limit
            if show_warning:
                credit = 0
                amount_total = 0
                if order.company_id.currency_id and  order.partner_id.commercial_partner_id.credit_limit_currency:
                    credit = order.company_id.currency_id._convert(
                        order.partner_id.commercial_partner_id.credit,
                        order.partner_id.commercial_partner_id.credit_limit_currency,
                        order.company_id,
                        order.date_order
                    )

                    amount_total = order.currency_id._convert(
                        order.amount_total,
                        order.partner_id.commercial_partner_id.credit_limit_currency,
                        order.company_id,
                        order.date_order
                    )

                #updated_credit = order.partner_id.commercial_partner_id.credit + (order.amount_total * order.currency_rate)
                updated_credit = credit + amount_total
                
                order.partner_credit_warning = self.env['account.move']._build_credit_warning_message(
                    order, updated_credit)