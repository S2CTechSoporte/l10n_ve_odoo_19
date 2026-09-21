from copy import deepcopy

from odoo import api, fields, models
from odoo.tools import formatLang


class AccountMove(models.Model):
    _inherit = "account.move"

    fcurrency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.fcurrency_id",
        string="Reference Currency",
        store=True,
    )
    same_currency = fields.Boolean(
        string="Document Uses Company Currency",
        compute="_compute_same_currency",
    )
    amount_untaxed_fcurrency = fields.Monetary(
        string="Untaxed Amount (Reference)",
        currency_field="fcurrency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_tax_fcurrency = fields.Monetary(
        string="Tax (Reference)",
        currency_field="fcurrency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_fcurrency = fields.Monetary(
        string="Total (Reference)",
        currency_field="fcurrency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_residual_fcurrency = fields.Monetary(
        string="Amount Due (Reference)",
        currency_field="fcurrency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_signed_fcurrency = fields.Monetary(
        string="Signed Total (Reference)",
        currency_field="fcurrency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_untaxed_local_currency = fields.Monetary(
        string="Untaxed Amount (VES)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_tax_local_currency = fields.Monetary(
        string="Tax (VES)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_local_currency = fields.Monetary(
        string="Total (VES)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_residual_local_currency = fields.Monetary(
        string="Amount Due (VES)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    amount_total_signed_local_currency = fields.Monetary(
        string="Signed Total (VES)",
        currency_field="company_currency_id",
        compute="_compute_dual_currency_amounts",
        store=True,
    )
    invoice_payments_widget_fcurrency = fields.Binary(
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

    def _get_dual_currency_reference_rate_date(self):
        """Return the rate date, preserving the source rate for local refunds."""
        self.ensure_one()
        if (
            self.move_type in ("out_refund", "in_refund")
            and self.reversed_entry_id
            and self.currency_id == self.company_currency_id
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
        "company_currency_id",
        "company_id.fcurrency_id",
        "invoice_date",
        "date",
        "reversed_entry_id.invoice_date",
        "reversed_entry_id.date",
        "line_ids.amount_residual_fcurrency",
    )
    def _compute_dual_currency_amounts(self):
        for move in self:
            company = move.company_id or self.env.company
            company_currency = move.company_currency_id or company.currency_id
            document_currency = move.currency_id or company_currency
            reference_currency = move.fcurrency_id or company_currency
            reference_date = move._get_dual_currency_reference_rate_date()
            document_date = move.invoice_date or move.date or fields.Date.context_today(move)

            move.amount_untaxed_fcurrency = document_currency.with_context(
                manual_rate=False
            )._convert(
                move.amount_untaxed,
                reference_currency,
                company,
                reference_date,
                False,
            )
            move.amount_tax_fcurrency = document_currency.with_context(
                manual_rate=False
            )._convert(
                move.amount_tax,
                reference_currency,
                company,
                reference_date,
                False,
            )
            move.amount_total_fcurrency = document_currency.with_context(
                manual_rate=False
            )._convert(
                move.amount_total,
                reference_currency,
                company,
                reference_date,
                False,
            )
            move.amount_total_signed_fcurrency = company_currency.with_context(
                manual_rate=False
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
                move.amount_residual_fcurrency = 0.0
            elif payment_term_lines:
                move.amount_residual_fcurrency = abs(
                    sum(payment_term_lines.mapped("amount_residual_fcurrency"))
                )
            else:
                move.amount_residual_fcurrency = document_currency.with_context(
                    manual_rate=False
                )._convert(
                    move.amount_residual,
                    reference_currency,
                    company,
                    reference_date,
                    False,
                )

            move.amount_untaxed_local_currency = document_currency.with_context(
                manual_rate=False
            )._convert(
                move.amount_untaxed,
                company_currency,
                company,
                document_date,
                False,
            )
            move.amount_tax_local_currency = document_currency.with_context(
                manual_rate=False
            )._convert(
                move.amount_tax,
                company_currency,
                company,
                document_date,
                False,
            )
            move.amount_total_local_currency = document_currency.with_context(
                manual_rate=False
            )._convert(
                move.amount_total,
                company_currency,
                company,
                document_date,
                False,
            )
            move.amount_residual_local_currency = document_currency.with_context(
                manual_rate=False
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
        "company_id.fcurrency_id",
    )
    def _compute_dual_currency_payment_widgets(self):
        for move in self:
            converted_widgets = {}
            for field_name, target_currency in (
                ("invoice_payments_widget_fcurrency", move.fcurrency_id),
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
                    payment_data["amount"] = source_currency.with_context(
                        manual_rate=False
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

            move.invoice_payments_widget_fcurrency = converted_widgets[
                "invoice_payments_widget_fcurrency"
            ]
            move.invoice_payments_widget_local_currency = converted_widgets[
                "invoice_payments_widget_local_currency"
            ]
