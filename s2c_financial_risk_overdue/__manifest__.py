{
    "name": "S2C Financial Risk Overdue",
    "summary": "Block sales when customers have overdue invoices",
    "version": "19.0.1.0.0",
    "author": "S2C Technology",
    "category": "Accounting",
    "license": "AGPL-3",
    "depends": ["account_financial_risk", "sale_financial_risk"],
    "data": [
        "views/res_partner_view.xml",
    ],
    "demo": [
        "demo/s2c_financial_risk_overdue_demo.xml",
    ],
    "installable": True,
    "application": False,
    "post_init_hook": "post_init_hook",
}