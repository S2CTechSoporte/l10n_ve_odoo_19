from odoo import api, models
from odoo.tools import SQL


class AccountReport(models.Model):
    _inherit = "account.report"

    def _init_options_dual_currency(self, options, previous_options):
        if options["report_id"] not in (
            self.env.ref("account_reports.partner_ledger_report").id,
            self.env.ref("account_reports.balance_sheet").id,
            self.env.ref("account_reports.customer_statement_report").id,
        ):
            return

        companies = self.env["res.company"].browse(self.get_report_company_ids(options))
        company_currency = companies[0].currency_id
        secondary_currency = companies[0].secondary_currency_id
        if any(
            company.currency_id != company_currency
            or company.secondary_currency_id != secondary_currency
            for company in companies
        ):
            return

        currencies = company_currency | secondary_currency
        options["dual_currency_general_filter"] = True
        selected_currency = currencies.filtered(
            lambda currency: currency.id
            == previous_options.get("dual_currency_id", company_currency.id)
        )[:1] or company_currency
        options["dual_currency_id"] = selected_currency.id
        options["dual_currencies"] = [
            {
                "currency_id": currency.id,
                "currency_name": currency.display_name,
                "currency_selected": currency == selected_currency,
            }
            for currency in currencies
        ]

    def _get_dual_currency_report(self, options):
        if options.get("report_id") not in (
            self.env.ref("account_reports.partner_ledger_report").id,
            self.env.ref("account_reports.balance_sheet").id,
            self.env.ref("account_reports.customer_statement_report").id,
        ):
            return self

        companies = self.env["res.company"].browse(self.get_report_company_ids(options))
        if not companies:
            return self
        company_currency = companies[0].currency_id
        secondary_currency = companies[0].secondary_currency_id
        if (
            secondary_currency
            and options.get("dual_currency_id") == secondary_currency.id
            and all(
                company.currency_id == company_currency
                and company.secondary_currency_id == secondary_currency
                for company in companies
            )
        ):
            return self.with_context(dual_currency_report=True)
        return self

    def get_report_information(self, options):
        report = self._get_dual_currency_report(options)
        return super(AccountReport, report).get_report_information(options)

    def _get_lines(self, options, all_column_groups_expression_totals=None, warnings=None):
        report = self._get_dual_currency_report(options)
        return super(AccountReport, report)._get_lines(
            options,
            all_column_groups_expression_totals=all_column_groups_expression_totals,
            warnings=warnings,
        )

    def get_expanded_lines(
        self,
        options,
        line_dict_id,
        groupby,
        expand_function_name,
        progress,
        offset,
        horizontal_split_side,
    ):
        report = self._get_dual_currency_report(options)
        return super(AccountReport, report).get_expanded_lines(
            options,
            line_dict_id,
            groupby,
            expand_function_name,
            progress,
            offset,
            horizontal_split_side,
        )

    @api.model
    def _currency_table_apply_rate(self, value: SQL) -> SQL:
        secondary_expressions = {
            "account_move_line.balance": "account_move_line.balance_secondary_currency",
            "account_move_line.debit": "account_move_line.debit_secondary_currency",
            "account_move_line.credit": "account_move_line.credit_secondary_currency",
            "CASE WHEN aml_with_partner.balance > 0 THEN 0 ELSE partial.amount END": (
                "CASE WHEN aml_with_partner.balance_secondary_currency > 0 "
                "THEN 0 ELSE partial.amount_secondary_currency END"
            ),
            "CASE WHEN aml_with_partner.balance < 0 THEN 0 ELSE partial.amount END": (
                "CASE WHEN aml_with_partner.balance_secondary_currency < 0 "
                "THEN 0 ELSE partial.amount_secondary_currency END"
            ),
            "-SIGN(aml_with_partner.balance) * partial.amount": (
                "-SIGN(aml_with_partner.balance_secondary_currency) "
                "* partial.amount_secondary_currency"
            ),
        }
        if self.env.context.get("dual_currency_report") and value.code in secondary_expressions:
            return SQL(secondary_expressions[value.code])
        return super()._currency_table_apply_rate(value)

    def _build_column_dict(
        self,
        col_value,
        col_data,
        options=None,
        currency=False,
        digits=1,
        column_expression=None,
        has_sublines=False,
        report_line_id=None,
    ):
        if options and options.get("dual_currency_id") and not currency:
            currency = self.env["res.currency"].browse(
                options["dual_currency_id"]
            )
        return super()._build_column_dict(
            col_value=col_value,
            col_data=col_data,
            options=options,
            currency=currency,
            digits=digits,
            column_expression=column_expression,
            has_sublines=has_sublines,
            report_line_id=report_line_id,
        )
