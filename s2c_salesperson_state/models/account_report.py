from odoo import fields, models


class AccountReport(models.Model):
    _inherit = "account.report"

    filter_salesperson = fields.Boolean(
        string="Salesperson",
        compute=lambda report: report._compute_report_option_filter("filter_salesperson"),
        precompute=True,
        readonly=False,
        store=True,
        depends=["root_report_id", "section_main_report_ids"],
    )
    filter_state = fields.Boolean(
        string="Zone",
        compute=lambda report: report._compute_report_option_filter("filter_state"),
        precompute=True,
        readonly=False,
        store=True,
        depends=["root_report_id", "section_main_report_ids"],
    )