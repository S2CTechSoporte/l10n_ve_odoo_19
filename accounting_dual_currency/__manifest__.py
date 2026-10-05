{
    "name": "Accounting Dual Currency",
    "summary": "Track accounting amounts in company and reference currencies",
    "author": "Juan Córdoba <jgcordobac@gmail.com>",
    "license": "LGPL-3",
    "category": "Accounting",
    "version": "19.0.1.1.0",
    "depends": [
        "account_reports",
        "currency_rate_live",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/account_move_views.xml",
        "views/account_move_line_views.xml",
        "views/account_payment_views.xml",
    ],
    "demo": [
        "demo/dual_currency_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "accounting_dual_currency/static/src/components/aged_partner_balance/**/*",
            "accounting_dual_currency/static/src/components/secondary_currency_menu/**/*",
        ],
        "web.assets_unit_tests": [
            "accounting_dual_currency/static/tests/secondary_currency_menu.test.js",
        ],
    },
    "installable": True,
}
