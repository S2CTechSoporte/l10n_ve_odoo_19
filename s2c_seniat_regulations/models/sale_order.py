from odoo import models, fields, api
from datetime import date, timedelta

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _compute_orders_without_invoice(self):
        last_month_start = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_end = last_month_start.replace(day=1) + timedelta(days=31)
        last_month_end = last_month_end.replace(day=1) - timedelta(days=1)

        sale_orders = self.env['sale.order'].search([
            ('state', '=', 'sale'),
            ('invoice_status', '=', 'to invoice'),
            ('date_order', '>=', last_month_start),
            ('date_order', '<=', last_month_end),
            ('company_id', '=', self.env.company.id),
        ])
        orders_without_invoice = len(sale_orders)
        return orders_without_invoice
