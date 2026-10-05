from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    secondary_currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="move_id.secondary_currency_id",
        string="Reference Currency",
        store=True,
    )
    conversion_rate = fields.Float(
        string="Reference Rate",
        compute="_compute_secondary_currency_fields",
        store=True,
        digits=0,
        help="Company-currency units for one unit of the reference currency.",
    )
    debit_secondary_currency = fields.Monetary(
        string="Debit (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_secondary_currency_fields",
        store=True,
    )
    credit_secondary_currency = fields.Monetary(
        string="Credit (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_secondary_currency_fields",
        store=True,
    )
    price_unit_secondary_currency = fields.Monetary(
        string="Unit Price (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_secondary_currency_fields",
        store=True,
    )
    price_subtotal_secondary_currency = fields.Monetary(
        string="Subtotal (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_secondary_currency_fields",
        store=True,
    )
    amount_residual_secondary_currency = fields.Monetary(
        string="Residual (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_secondary_currency_fields",
        store=True,
    )
    balance_secondary_currency = fields.Monetary(
        string="Balance (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_secondary_currency_fields",
        store=True,
    )
    date_maturity_secondary_currency = fields.Date(
        string="Dual Currency Due Date",
        compute="_compute_date_maturity_secondary_currency",
        store=True,
        index=True,
    )

    @api.depends("date", "date_maturity")
    def _compute_date_maturity_secondary_currency(self):
        for line in self:
            line.date_maturity_secondary_currency = line.date_maturity or line.date

    @api.depends(
        "company_id.secondary_currency_id",
        "company_currency_id",
        "currency_id",
        "balance",
        "debit",
        "credit",
        "amount_residual",
        "price_unit",
        "price_subtotal",
        "move_id.invoice_date",
        "move_id.date",
        "move_id.reversed_entry_id.invoice_date",
        "move_id.reversed_entry_id.date",
        "matched_debit_ids.amount_secondary_currency",
        "matched_credit_ids.amount_secondary_currency",
    )
    def _compute_secondary_currency_fields(self):
        for line in self:
            company = line.company_id or self.env.company
            company_currency = line.company_currency_id or company.currency_id
            reference_currency = line.secondary_currency_id or company_currency
            source_currency = line.currency_id or company_currency
            rate_date = line.move_id._get_dual_currency_reference_rate_date()

            conversion_rate = self.env["res.currency"].with_context(
                manual_rate=False
            )._get_conversion_rate(
                from_currency=company_currency,
                to_currency=reference_currency,
                company=company,
                date=rate_date,
            )
            line.conversion_rate = 1.0 / conversion_rate if conversion_rate else 0.0
            line.balance_secondary_currency = company_currency.with_context(
                manual_rate=False
            )._convert(
                line.balance,
                reference_currency,
                company,
                rate_date,
                False,
            )
            line.debit_secondary_currency = company_currency.with_context(
                manual_rate=False
            )._convert(
                line.debit,
                reference_currency,
                company,
                rate_date,
                False,
            )
            line.credit_secondary_currency = company_currency.with_context(
                manual_rate=False
            )._convert(
                line.credit,
                reference_currency,
                company,
                rate_date,
                False,
            )
            line.price_unit_secondary_currency = source_currency.with_context(
                manual_rate=False
            )._convert(
                line.price_unit,
                reference_currency,
                company,
                rate_date,
                False,
            )
            line.price_subtotal_secondary_currency = source_currency.with_context(
                manual_rate=False
            )._convert(
                line.price_subtotal,
                reference_currency,
                company,
                rate_date,
                False,
            )

            residual = (
                line.balance_secondary_currency
                - sum(line.matched_credit_ids.mapped("amount_secondary_currency"))
                + sum(line.matched_debit_ids.mapped("amount_secondary_currency"))
            )
            line.amount_residual_secondary_currency = (
                0.0 if company_currency.is_zero(line.amount_residual) else residual
            )
