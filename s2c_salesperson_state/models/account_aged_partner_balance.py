from odoo import models


class AccountAgedPartnerBalanceReportHandler(models.AbstractModel):
    _inherit = "account.aged.receivable.report.handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)

        previous_options = previous_options or {}
        has_custom_filter = False

        if report.filter_salesperson:
            salesperson_ids = [
                int(record_id)
                for record_id in previous_options.get("salesperson_ids", [])
            ]
            selected_salespersons = self.env["res.users"].with_context(
                active_test=False
            ).search([("id", "in", salesperson_ids)])
            options["salesperson_ids"] = selected_salespersons.ids
            if selected_salespersons:
                options.setdefault("forced_domain", []).append(
                    ("move_id.invoice_user_id", "in", selected_salespersons.ids)
                )
            has_custom_filter = True

        if report.filter_state:
            state_ids = [
                int(record_id)
                for record_id in previous_options.get("state_ids", [])
            ]
            selected_states = self.env["res.country.state"].search(
                [("id", "in", state_ids)]
            )
            options["state_ids"] = selected_states.ids
            if selected_states:
                options.setdefault("forced_domain", []).append(
                    ("partner_id.state_id", "in", selected_states.ids)
                )
            has_custom_filter = True

        if has_custom_filter:
            options.setdefault("custom_display_config", {}).setdefault(
                "components", {}
            )["AccountReportFilters"] = "S2CSalespersonStateAgedPartnerBalanceFilters"

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
        empty_values = {"salesperson": None, "state": None}

        if not current_groupby:
            result.update(empty_values)
            return result

        if current_groupby != "id":
            for _grouping_key, values in result:
                values.update(empty_values)
            return result

        move_lines = self.env["account.move.line"].browse(
            grouping_key for grouping_key, _values in result if grouping_key
        ).exists()
        values_by_move_line_id = {
            move_line.id: {
                "salesperson": move_line.move_id.invoice_user_id.display_name or None,
                "state": move_line.partner_id.state_id.display_name or None,
            }
            for move_line in move_lines
        }
        for grouping_key, values in result:
            values.update(values_by_move_line_id.get(grouping_key, empty_values))

        return result

    def _prepare_partner_values(self):
        values = super()._prepare_partner_values()
        values.update({"salesperson": None, "state": None})
        return values