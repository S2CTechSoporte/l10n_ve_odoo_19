from copy import deepcopy

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, formatLang


class AccountMove(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "dual.currency.manual.rate.mixin"]

    manual_rate = fields.Boolean(tracking=True)
    manual_conversion_rate = fields.Float(tracking=True)
    secondary_currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.secondary_currency_id",
        string="Reference Currency",
        store=True,
    )
    same_currency = fields.Boolean(
        string="Document Uses Company Currency",
        compute="_compute_same_currency",
    )
    conversion_rate = fields.Float(
        string="Reference Rate",
        compute="_compute_dual_currency_amounts",
        store=True,
        digits=0,
        help="Company-currency units for one unit of the reference currency.",
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
    amount_untaxed_secondary_currency = fields.Monetary(
        string="Untaxed Amount (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_tax_secondary_currency = fields.Monetary(
        string="Tax (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_secondary_currency = fields.Monetary(
        string="Total (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_residual_secondary_currency = fields.Monetary(
        string="Amount Due (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_signed_secondary_currency = fields.Monetary(
        string="Signed Total (Reference)",
        currency_field="secondary_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_untaxed_local_currency = fields.Monetary(
        string="Untaxed Amount (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_tax_local_currency = fields.Monetary(
        string="Tax (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_local_currency = fields.Monetary(
        string="Total (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_residual_local_currency = fields.Monetary(
        string="Amount Due (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_signed_local_currency = fields.Monetary(
        string="Signed Total (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    invoice_payments_widget_secondary_currency = fields.Binary(
        groups="account.group_account_invoice,account.group_account_readonly",
        compute="_compute_dual_currency_payment_widgets",
        exportable=False,
    )
    invoice_payments_widget_local_currency = fields.Binary(
        groups="account.group_account_invoice,account.group_account_readonly",
        compute="_compute_dual_currency_payment_widgets",
        exportable=False,
    )

    @api.depends("currency_id", "company_currency_id")
    def _compute_same_currency(self):
        for move in self:
            move.same_currency = move.currency_id == move.company_currency_id

    @api.depends("conversion_rate", "company_currency_id", "secondary_currency_id")
    def _compute_conversion_rate_display(self):
        for move in self:
            company = move.company_id or self.env.company
            move.update(company._get_conversion_rate_display(move.conversion_rate))

    def _get_manual_rate_date(self):
        return self._get_dual_currency_reference_rate_date()

    def _is_manual_rate_document(self):
        """Invoices own a rate; entries only when they are the entry of a payment."""
        return self.move_type != "entry" or bool(self.origin_payment_id)

    @api.depends("move_type", "origin_payment_id")
    def _compute_manual_rate_available(self):
        super()._compute_manual_rate_available()

    @api.depends("manual_rate", "manual_conversion_rate")
    def _compute_expected_currency_rate(self):
        super()._compute_expected_currency_rate()

    @api.depends("manual_rate", "manual_conversion_rate")
    def _compute_invoice_currency_rate(self):
        super()._compute_invoice_currency_rate()

    def _get_expected_currency_rate_at(self, date):
        """Return the manual rate instead of the system rate when the document has one."""
        return super(AccountMove, self._with_manual_rate())._get_expected_currency_rate_at(
            date
        )

    def _compute_payments_widget_to_reconcile_info(self):
        """Show the outstanding payments of another currency at their own manual rate."""
        super()._compute_payments_widget_to_reconcile_info()
        for move in self:
            widget = deepcopy(move.invoice_outstanding_credits_debits_widget)
            if not widget:
                continue
            for payment_data in widget.get("content", []):
                line = self.env["account.move.line"].browse(payment_data["id"])
                if line.currency_id == move.currency_id or not line.move_id.manual_rate:
                    continue
                payment_data["amount"] = line.company_currency_id.with_context(
                    **line.move_id._get_dual_currency_conversion_context()
                )._convert(
                    abs(line.amount_residual),
                    move.currency_id,
                    move.company_id,
                    line.date,
                )
            move.invoice_outstanding_credits_debits_widget = widget

    def write(self, vals):
        manual_fields = {"manual_rate", "manual_conversion_rate"} & vals.keys()
        if manual_fields:
            for move in self.filtered(lambda move: move.state == "posted"):
                if any(move[name] != vals[name] for name in manual_fields):
                    raise UserError(
                        _(
                            "You cannot modify the manual rate of the posted document "
                            "%(move)s. Reset it to draft first.",
                            move=move.name or move.ref or move.id,
                        )
                    )
        return super().write(vals)

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """Credit notes keep the manual rate of the invoice they reverse."""
        if not default_values_list:
            default_values_list = [{} for _move in self]
        for move, default_values in zip(self, default_values_list):
            if move.manual_rate and move.is_invoice(include_receipts=True):
                default_values.setdefault("manual_rate", True)
                default_values.setdefault(
                    "manual_conversion_rate", move.manual_conversion_rate
                )
        return super()._reverse_moves(default_values_list, cancel=cancel)

    def _keeps_reversed_entry_currency_rate(self):
        """Whether the credit note keeps the currency rate of the invoice it reverses.

        The reversal wizard of Odoo copies the rate of the invoice, so the credit note
        cancels it in company currency. A credit note in company currency always keeps
        it, because it has no conversion to the company currency.
        """
        self.ensure_one()
        if self.currency_id == self.company_currency_id:
            return True
        return float_is_zero(
            self.invoice_currency_rate - self.reversed_entry_id.invoice_currency_rate,
            precision_digits=12,
        )

    def _get_dual_currency_reference_rate_date(self):
        """Return the rate date, preserving the source rate for credit notes."""
        self.ensure_one()
        if (
            self.move_type in ("out_refund", "in_refund")
            and self.reversed_entry_id
            and self._keeps_reversed_entry_currency_rate()
        ):
            return (
                self.reversed_entry_id.invoice_date
                or self.reversed_entry_id.date
                or self.invoice_date
                or self.date
                or fields.Date.context_today(self)
            )
        return self.invoice_date or self.date or fields.Date.context_today(self)

    @api.depends(
        "amount_untaxed",
        "amount_tax",
        "amount_total",
        "amount_residual",
        "amount_total_signed",
        "currency_id",
        "move_type",
        "company_currency_id",
        "company_id.secondary_currency_id",
        "invoice_date",
        "date",
        "reversed_entry_id.invoice_date",
        "reversed_entry_id.date",
        "invoice_currency_rate",
        "reversed_entry_id.invoice_currency_rate",
        "line_ids.amount_residual_secondary_currency",
        "manual_rate",
        "manual_conversion_rate",
    )
    def _compute_dual_currency_amounts(self):
        for move in self:
            company = move.company_id or self.env.company
            company_currency = move.company_currency_id or company.currency_id
            document_currency = move.currency_id or company_currency
            reference_currency = move.secondary_currency_id or company_currency
            reference_date = move._get_dual_currency_reference_rate_date()
            document_date = reference_date
            conversion_context = move._get_dual_currency_conversion_context()

            conversion_rate = self.env["res.currency"].with_context(
                **conversion_context
            )._get_conversion_rate(
                from_currency=company_currency,
                to_currency=reference_currency,
                company=company,
                date=reference_date,
            )
            move.conversion_rate = 1.0 / conversion_rate if conversion_rate else 0.0

            move.amount_untaxed_secondary_currency = document_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_untaxed,
                reference_currency,
                company,
                reference_date,
                False,
            )
            move.amount_tax_secondary_currency = document_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_tax,
                reference_currency,
                company,
                reference_date,
                False,
            )
            move.amount_total_secondary_currency = document_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_total,
                reference_currency,
                company,
                reference_date,
                False,
            )
            move.amount_total_signed_secondary_currency = company_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_total_signed,
                reference_currency,
                company,
                reference_date,
                False,
            )

            payment_term_lines = move.line_ids.filtered(
                lambda line: line.account_id.account_type
                in ("asset_receivable", "liability_payable")
            )
            if document_currency.is_zero(move.amount_residual):
                move.amount_residual_secondary_currency = 0.0
            elif payment_term_lines:
                move.amount_residual_secondary_currency = abs(
                    sum(payment_term_lines.mapped("amount_residual_secondary_currency"))
                )
            else:
                move.amount_residual_secondary_currency = document_currency.with_context(
                    **conversion_context
                )._convert(
                    move.amount_residual,
                    reference_currency,
                    company,
                    reference_date,
                    False,
                )

            move.amount_untaxed_local_currency = document_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_untaxed,
                company_currency,
                company,
                document_date,
                False,
            )
            move.amount_tax_local_currency = document_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_tax,
                company_currency,
                company,
                document_date,
                False,
            )
            move.amount_total_local_currency = document_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_total,
                company_currency,
                company,
                document_date,
                False,
            )
            move.amount_residual_local_currency = document_currency.with_context(
                **conversion_context
            )._convert(
                move.amount_residual,
                company_currency,
                company,
                document_date,
                False,
            )
            move.amount_total_signed_local_currency = move.amount_total_signed

    @api.depends(
        "invoice_payments_widget",
        "currency_id",
        "company_currency_id",
        "company_id.secondary_currency_id",
    )
    def _compute_dual_currency_payment_widgets(self):
        for move in self:
            converted_widgets = {}
            for field_name, target_currency in (
                ("invoice_payments_widget_secondary_currency", move.secondary_currency_id),
                (
                    "invoice_payments_widget_local_currency",
                    move.company_currency_id,
                ),
            ):
                widget = deepcopy(move.invoice_payments_widget)
                if not widget or not target_currency:
                    converted_widgets[field_name] = False
                    continue

                for payment_data in widget.get("content", []):
                    source_currency = self.env["res.currency"].browse(
                        payment_data.get("currency_id")
                    ) or move.currency_id
                    payment_date = (
                        fields.Date.to_date(payment_data["date"])
                        if payment_data.get("date")
                        else move.date
                    )
                    payment_move = (
                        self.env["account.move"].sudo().browse(payment_data.get("move_id"))
                    )
                    conversion_context = (
                        payment_move._get_dual_currency_conversion_context()
                        if payment_move
                        else {"manual_rate": False, "dual_currency_manual_rate": False}
                    )
                    payment_data["amount"] = source_currency.with_context(
                        **conversion_context
                    )._convert(
                        payment_data.get("amount", 0.0),
                        target_currency,
                        move.company_id,
                        payment_date,
                        False,
                    )
                    payment_data["currency_id"] = target_currency.id
                    payment_data["amount_company_currency"] = formatLang(
                        self.env,
                        abs(payment_data["amount"]),
                        currency_obj=target_currency,
                    )
                    payment_data["amount_foreign_currency"] = False
                converted_widgets[field_name] = widget

            move.invoice_payments_widget_secondary_currency = converted_widgets[
                "invoice_payments_widget_secondary_currency"
            ]
            move.invoice_payments_widget_local_currency = converted_widgets[
                "invoice_payments_widget_local_currency"
            ]
