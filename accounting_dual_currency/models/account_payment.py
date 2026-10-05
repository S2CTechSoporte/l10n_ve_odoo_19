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
    conversion_rate_display_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Rate Display Currency",
        compute="_compute_conversion_rate_display",
    )
    conversion_rate_display_is_usd = fields.Boolean(
        string="Rate Display Uses USD",
        compute="_compute_conversion_rate_display",
    )
    conversion_rate_display = fields.Monetary(
        string="USD Rate",
        currency_field="conversion_rate_display_currency_id",
        compute="_compute_conversion_rate_display",
    )
    amount_local = fields.Monetary(
        string="Amount (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_ref = fields.Monetary(
        string="Amount (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    secondary_currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.secondary_currency_id",
        string="Reference Currency",
        store=True,
    )

    @api.depends("conversion_rate", "company_currency_id", "secondary_currency_id")
    def _compute_conversion_rate_display(self):
        for payment in self:
            company = payment.company_id or self.env.company
            payment.update(company._get_conversion_rate_display(payment.conversion_rate))

    @api.depends(
        "currency_id",
        "amount",
        "date",
        "company_id.currency_id",
        "company_id.secondary_currency_id",
    )
    def _compute_dual_currency_amounts(self):
        for payment in self:
            company = payment.company_id or self.env.company
            company_currency = payment.company_currency_id or company.currency_id
            payment_currency = payment.currency_id or company_currency
            reference_currency = payment.secondary_currency_id or company_currency
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
