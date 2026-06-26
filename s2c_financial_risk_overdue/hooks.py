from datetime import timedelta

from odoo import fields


def post_init_hook(env):
    demo_invoice = env.ref(
        "s2c_financial_risk_overdue.invoice_demo_financial_risk_overdue",
        raise_if_not_found=False,
    )
    if not demo_invoice or demo_invoice.state != "draft":
        return
    demo_invoice.invoice_date_due = fields.Date.today() - timedelta(days=5)
    demo_invoice.action_post()