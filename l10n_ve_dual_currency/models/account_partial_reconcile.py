from odoo import api, fields, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    company_fcurrency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.fcurrency_id",
        string="Company Reference Currency",
    )
    amount_fcurrency = fields.Monetary(
        string="Amount (Reference)",
        currency_field="company_fcurrency_id",
        compute="_compute_amount_fcurrency",
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
        "company_id.fcurrency_id",
    )
    def _compute_amount_fcurrency(self):
        for partial in self:
            company = partial.company_id or self.env.company
            company_currency = company.currency_id
            reference_currency = company.fcurrency_id or company_currency
            if partial.debit_currency_id == reference_currency:
                partial.amount_fcurrency = partial.debit_amount_currency
            elif partial.credit_currency_id == reference_currency:
                partial.amount_fcurrency = partial.credit_amount_currency
            else:
                partial.amount_fcurrency = company_currency.with_context(
                    manual_rate=False
                )._convert(
                    partial.amount,
                    reference_currency,
                    company,
                    partial.max_date or fields.Date.context_today(partial),
                    False,
                )
