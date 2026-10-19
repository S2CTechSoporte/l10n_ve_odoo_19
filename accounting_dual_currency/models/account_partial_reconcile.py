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

    def _get_dual_currency_conversion_context(self):
        """Return the conversion context of the document that settles the partial.

        A payment settles an invoice at its own rate, so the manual rate of the payment
        wins; then comes an invoice, and a journal entry is the last resort. Within each
        kind, the latest document that has a manual rate is used.
        """
        self.ensure_one()
        manual_moves = (
            (self.debit_move_id | self.credit_move_id).move_id.filtered("manual_rate")
        ).sorted(
            key=lambda move: (
                0
                if move.origin_payment_id
                else 1 if move.is_invoice(include_receipts=True) else 2,
                -move.date.toordinal() if move.date else 0,
            )
        )
        for move in manual_moves:
            if move._get_manual_rate_spec():
                return move._get_dual_currency_conversion_context()
        return {"manual_rate": False, "dual_currency_manual_rate": False}

    @api.depends(
        "amount",
        "debit_amount_currency",
        "credit_amount_currency",
        "debit_currency_id",
        "credit_currency_id",
        "max_date",
        "company_id.currency_id",
        "company_id.secondary_currency_id",
        "debit_move_id.move_id.manual_rate",
        "debit_move_id.move_id.manual_conversion_rate",
        "credit_move_id.move_id.manual_rate",
        "credit_move_id.move_id.manual_conversion_rate",
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
                    **partial._get_dual_currency_conversion_context()
                )._convert(
                    partial.amount,
                    reference_currency,
                    company,
                    partial.max_date or fields.Date.context_today(partial),
                    False,
                )
