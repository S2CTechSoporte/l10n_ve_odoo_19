{
    "name": "S2C Salesperson and Zone",
    "summary": "Adds salesperson and customer zone filters to sales and accounting",
    "version": "19.0.1.1.0",
    "author": "S2C Technology, C.A.",
    "category": "Sales",
    "license": "AGPL-3",
    "depends": ["sale", "account_reports"],
    "data": [
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/account_report_views.xml",
        "data/account_aged_receivable_report.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "s2c_salesperson_state/static/src/components/**/*.js",
            "s2c_salesperson_state/static/src/components/**/*.xml",
        ],
    },
    "installable": True,
    "application": False,
}