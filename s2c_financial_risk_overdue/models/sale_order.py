from odoo import _, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def evaluate_risk_message(self, partner):
        self.ensure_one()
        if partner.risk_account_overdue_invoices and not partner.risk_currency_id.is_zero(
            partner.risk_amount_overdue_invoices
        ):
            return _("This customer has overdue invoices.\n")
        return super().evaluate_risk_message(partner)