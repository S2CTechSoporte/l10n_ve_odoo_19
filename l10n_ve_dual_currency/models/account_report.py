from odoo import models


class AccountReport(models.Model):
    _inherit = "account.report"

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
