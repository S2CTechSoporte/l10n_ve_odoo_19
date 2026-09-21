from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    currency_equal = fields.Boolean(
        string="Uses Foreign Currency",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    conversion_rate = fields.Float(
        string="Reference Rate",
        compute="_compute_dual_currency_amounts",
        store=True,
        digits=0,
    )
    amount_local = fields.Monetary(
        string="Amount (VES)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_ref = fields.Monetary(
        string="Amount (Reference)",
        currency_field="fcurrency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    fcurrency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.fcurrency_id",
        string="Reference Currency",
        store=True,
    )

    @api.depends(
        "currency_id",
        "amount",
        "date",
        "company_id.currency_id",
        "company_id.fcurrency_id",
    )
    def _compute_dual_currency_amounts(self):
        for payment in self:
            company = payment.company_id or self.env.company
            company_currency = payment.company_currency_id or company.currency_id
            payment_currency = payment.currency_id or company_currency
            reference_currency = payment.fcurrency_id or company_currency
            payment_date = payment.date or fields.Date.context_today(payment)

            conversion_rate = self.env["res.currency"].with_context(
                manual_rate=False
            )._get_conversion_rate(
                from_currency=company_currency,
                to_currency=reference_currency,
                company=company,
                date=payment_date,
            )
            payment.conversion_rate = (
                1.0 / conversion_rate if conversion_rate else 0.0
            )
            payment.amount_local = payment_currency.with_context(
                manual_rate=False
            )._convert(
                payment.amount,
                company_currency,
                company,
                payment_date,
                False,
            )
            payment.amount_ref = payment_currency.with_context(
                manual_rate=False
            )._convert(
                payment.amount,
                reference_currency,
                company,
                payment_date,
                False,
            )
            payment.currency_equal = payment_currency != company_currency
