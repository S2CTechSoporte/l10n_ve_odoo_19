from odoo import api, fields, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    company_secondary_currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.secondary_currency_id",
        string="Company Reference Currency",
    )
    amount_secondary_currency = fields.Monetary(
        string="Amount (Reference)",
        currency_field="company_secondary_currency_id",
        compute="_compute_amount_secondary_currency",
        store=True,
    )

    @api.depends(
        "amount",
        "debit_amount_currency",
        "credit_amount_currency",
        "debit_currency_id",
        "credit_currency_id",
        "max_date",
        "company_id.currency_id",
        "company_id.secondary_currency_id",
    )
    def _compute_amount_secondary_currency(self):
        for partial in self:
            company = partial.company_id or self.env.company
            company_currency = company.currency_id
            reference_currency = company.secondary_currency_id or company_currency
            if partial.debit_currency_id == reference_currency:
                partial.amount_secondary_currency = partial.debit_amount_currency
            elif partial.credit_currency_id == reference_currency:
                partial.amount_secondary_currency = partial.credit_amount_currency
            else:
                partial.amount_secondary_currency = company_currency.with_context(
                    manual_rate=False
                )._convert(
                    partial.amount,
                    reference_currency,
                    company,
                    partial.max_date or fields.Date.context_today(partial),
                    False,
                )
