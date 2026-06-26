from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    risk_account_overdue_invoices = fields.Boolean(
        string="Block Sales With Overdue Invoices",
        help="If enabled, sale orders are blocked when the customer has overdue "
        "customer invoices with pending balance.",
    )
    risk_amount_overdue_invoices = fields.Monetary(
        string="Overdue Customer Invoices",
        currency_field="risk_currency_id",
        compute="_compute_risk_account_amount",
        compute_sudo=True,
        help="Pending balance of overdue customer invoices.",
    )

    @api.depends(
        "move_line_ids",
        "move_line_ids.amount_residual",
        "move_line_ids.amount_residual_currency",
        "move_line_ids.date_maturity",
        "move_line_ids.date",
        "move_line_ids.parent_state",
        "move_line_ids.reconciled",
        "move_line_ids.account_id",
        "move_line_ids.move_id.move_type",
        "company_id.invoice_unpaid_margin",
    )
    def _compute_risk_account_amount(self):
        self.update({"risk_amount_overdue_invoices": 0.0})
        return super()._compute_risk_account_amount()

    @api.model
    def _risk_account_groups(self):
        groups = super()._risk_account_groups()
        max_date = self._max_risk_date_due()
        groups["overdue_invoice"] = {
            "domain": self._get_risk_company_domain()
            + [
                ("reconciled", "=", False),
                ("account_type", "=", "asset_receivable"),
                "|",
                "&",
                ("date_maturity", "!=", False),
                ("date_maturity", "<", max_date),
                "&",
                ("date_maturity", "=", False),
                ("date", "<", max_date),
                ("parent_state", "=", "posted"),
                ("move_id.move_type", "=", "out_invoice"),
            ],
            "fields": ["amount_residual:sum", "amount_residual_currency:sum"],
            "group_by": ["partner_id", "account_id", "currency_id"],
        }
        return groups

    def _prepare_risk_account_vals(self, groups):
        vals = super()._prepare_risk_account_vals(groups)
        vals["risk_amount_overdue_invoices"] = 0.0
        for (
            partner,
            account,
            currency,
            amount_residual,
            amount_residual_currency,
        ) in groups["overdue_invoice"]["read_group"]:
            if partner.id not in self.ids:
                continue
            vals["risk_amount_overdue_invoices"] += self._get_amount_in_risk_currency(
                currency,
                amount_residual_currency,
                amount_residual,
                account,
            )
        return vals

    def _get_field_risk_model_domain(self, field_name):
        if field_name == "risk_amount_overdue_invoices":
            domain = self._risk_account_groups()["overdue_invoice"]["domain"] + [
                ("partner_id", "in", self.ids)
            ]
            return "account.move.line", domain
        return super()._get_field_risk_model_domain(field_name)

    def _get_amount_in_risk_currency(
        self, currency, amount_residual_currency, amount_residual, account
    ):
        company = getattr(account, "company_id", False) or account.company_ids[:1]
        company = company or self.company_id
        acc_currency_id = company.currency_id.id
        risk_currency_id = self.risk_currency_id.id
        if currency.id == risk_currency_id:
            return amount_residual_currency
        if acc_currency_id == risk_currency_id:
            return amount_residual
        return company.currency_id._convert(
            amount_residual,
            self.risk_currency_id,
            company,
            fields.Date.context_today(self),
            round=False,
        )