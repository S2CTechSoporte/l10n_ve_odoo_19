from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _name = "account.payment"
    _inherit = ["account.payment", "dual.currency.manual.rate.mixin"]

    manual_rate = fields.Boolean(tracking=True)
    manual_conversion_rate = fields.Float(tracking=True)
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

    def _get_manual_rate_date(self):
        return self.date or fields.Date.context_today(self)

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
        "manual_rate",
        "manual_conversion_rate",
    )
    def _compute_dual_currency_amounts(self):
        for payment in self:
            company = payment.company_id or self.env.company
            company_currency = payment.company_currency_id or company.currency_id
            payment_currency = payment.currency_id or company_currency
            reference_currency = payment.secondary_currency_id or company_currency
            payment_date = payment.date or fields.Date.context_today(payment)
            conversion_context = payment._get_dual_currency_conversion_context()

            conversion_rate = self.env["res.currency"].with_context(
                **conversion_context
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
                **conversion_context
            )._convert(
                payment.amount,
                company_currency,
                company,
                payment_date,
                False,
            )
            payment.amount_ref = payment_currency.with_context(
                **conversion_context
            )._convert(
                payment.amount,
                reference_currency,
                company,
                payment_date,
                False,
            )
            payment.currency_equal = payment_currency != company_currency

    @api.depends("manual_rate", "manual_conversion_rate")
    def _compute_amount_company_currency_signed(self):
        manual_payments = self.filtered("manual_rate")
        super(AccountPayment, self - manual_payments)._compute_amount_company_currency_signed()
        for payment in manual_payments:
            super(
                AccountPayment, payment._with_manual_rate()
            )._compute_amount_company_currency_signed()

    def write(self, vals):
        manual_fields = {"manual_rate", "manual_conversion_rate"} & vals.keys()
        if manual_fields:
            for payment in self.filtered(lambda payment: payment.state != "draft"):
                if any(payment[name] != vals[name] for name in manual_fields):
                    raise UserError(
                        _(
                            "You cannot modify the manual rate of a payment that is not "
                            "in draft. Reset it to draft first."
                        )
                    )
        return super().write(vals)

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        return (
            *super()._get_trigger_fields_to_synchronize(),
            "manual_rate",
            "manual_conversion_rate",
        )

    def _prepare_move_lines_per_type(self, write_off_line_vals=None, force_balance=None):
        """Convert the journal items of the payment at its manual rate, when it has one."""
        return super(
            AccountPayment, self._with_manual_rate()
        )._prepare_move_lines_per_type(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )

    def _get_manual_rate_move_vals(self):
        """Return the manual rate values of the journal entry of the payment."""
        self.ensure_one()
        if self._get_manual_rate_spec():
            return {
                "manual_rate": True,
                "manual_conversion_rate": self.manual_conversion_rate,
            }
        return {"manual_rate": False, "manual_conversion_rate": 0.0}

    def _generate_move_vals(self, write_off_line_vals=None, force_balance=None, line_ids=None):
        move_vals = super()._generate_move_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
            line_ids=line_ids,
        )
        move_vals.update(self._get_manual_rate_move_vals())
        return move_vals

    def _synchronize_to_moves(self, changed_fields):
        super()._synchronize_to_moves(changed_fields)
        for payment in self:
            move = payment.move_id
            if move.state != "draft":
                continue
            move_vals = payment._get_manual_rate_move_vals()
            if any(move[field_name] != value for field_name, value in move_vals.items()):
                move.with_context(skip_invoice_sync=True).write(move_vals)
