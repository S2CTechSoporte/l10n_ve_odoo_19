from dateutil.relativedelta import relativedelta

from odoo import fields, models


class AgedPartnerBalanceCustomHandler(models.AbstractModel):
    _inherit = "account.aged.partner.balance.report.handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(
            report,
            options,
            previous_options=previous_options,
        )
        previous_options = previous_options or {}
        company_currency = self.env.company.currency_id
        currencies = company_currency | self.env.company.fcurrency_id
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
        options["multi_currency"] = options.get("multi_currency") or len(currencies) > 1

    def _aged_partner_report_custom_engine_common(
        self,
        options,
        internal_type,
        current_groupby,
        next_groupby,
        offset=0,
        limit=None,
    ):
        result = super()._aged_partner_report_custom_engine_common(
            options,
            internal_type,
            current_groupby,
            next_groupby,
            offset=offset,
            limit=limit,
        )
        selected_currency = self.env["res.currency"].browse(
            options.get("dual_currency_id")
        )
        if (
            not selected_currency
            or selected_currency
            not in (self.env.company.currency_id | self.env.company.fcurrency_id)
            or current_groupby not in (None, "partner_id", "id")
        ):
            return result

        periods = self._get_dual_currency_periods(options)
        if isinstance(result, dict):
            values = self._get_dual_currency_period_values(
                options,
                internal_type,
                periods,
            )
            result.update(
                {
                    **{f"period{i}": value for i, value in enumerate(values)},
                    "total": sum(values),
                }
            )
            return result

        for grouping_key, values_dict in result:
            values = self._get_dual_currency_period_values(
                options,
                internal_type,
                periods,
                partner_id=grouping_key if current_groupby == "partner_id" else None,
                line_id=grouping_key if current_groupby == "id" else None,
            )
            values_dict.update(
                {
                    **{f"period{i}": value for i, value in enumerate(values)},
                    "total": sum(values) if current_groupby != "id" else None,
                }
            )
        return result

    def _get_dual_currency_periods(self, options):
        """Build the same aging periods used by the Odoo 19 report engine."""
        date_to = fields.Date.to_date(options["date"]["date_to"])
        interval = options.get("aging_interval", 30)
        periods = [(False, date_to)]
        column_group_count = max(len(options.get("column_groups", {})), 1)
        period_column_count = len(
            [
                column
                for column in options["columns"]
                if column["expression_label"].startswith("period")
            ]
        )
        period_count = period_column_count // column_group_count - 1
        for index in range(period_count):
            date_start = date_to - relativedelta(days=(interval * index) + 1)
            date_stop = (
                date_to - relativedelta(days=interval * (index + 1))
                if index < period_count - 1
                else False
            )
            periods.append((date_start, date_stop))
        return periods

    def _get_dual_currency_period_values(
        self,
        options,
        internal_type,
        periods,
        partner_id=None,
        line_id=None,
    ):
        """Compute aged residuals from reference balances at the report cutoff."""
        report = self.env["account.report"].browse(options["report_id"])
        domain = [
            *report._get_options_domain(options, "from_beginning"),
            ("account_id.account_type", "=", internal_type),
        ]
        if partner_id is not None:
            domain.append(("partner_id", "=", partner_id))
        if line_id is not None:
            domain.append(("id", "=", line_id))

        report_date = fields.Date.to_date(options["date"]["date_to"])
        exchange_journal = self.env.company.currency_exchange_journal_id
        multiplicator = -1 if internal_type == "liability_payable" else 1
        selected_currency = self.env["res.currency"].browse(
            options["dual_currency_id"]
        )
        use_reference_currency = selected_currency == self.env.company.fcurrency_id
        period_values = [0.0] * len(periods)

        for line in self.env["account.move.line"].search(domain):
            aging_date = (
                line.invoice_date
                if options.get("aging_based_on") == "base_on_invoice_date"
                else line.date_maturity or line.date
            )
            period_index = next(
                (
                    index
                    for index, (date_start, date_stop) in enumerate(periods)
                    if (not date_start or aging_date <= date_start)
                    and (not date_stop or aging_date >= date_stop)
                ),
                None,
            )
            if period_index is None:
                continue

            matched_credits = line.matched_credit_ids.filtered(
                lambda partial: partial.max_date <= report_date
                and (
                    not exchange_journal
                    or partial.credit_move_id.journal_id != exchange_journal
                )
            )
            matched_debits = line.matched_debit_ids.filtered(
                lambda partial: partial.max_date <= report_date
                and (
                    not exchange_journal
                    or partial.debit_move_id.journal_id != exchange_journal
                )
            )
            if use_reference_currency:
                residual = (
                    line.balance_fcurrency
                    - sum(matched_credits.mapped("amount_fcurrency"))
                    + sum(matched_debits.mapped("amount_fcurrency"))
                )
            else:
                residual = (
                    line.balance
                    - sum(matched_credits.mapped("amount"))
                    + sum(matched_debits.mapped("amount"))
                )
            period_values[period_index] += multiplicator * residual

        return [selected_currency.round(value) for value in period_values]
