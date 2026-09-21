{
    "name": "Venezuela Dual Currency",
    "summary": "Track Venezuelan accounting documents in VES and a reference currency",
    "author": "Juan Córdoba <jgcordobac@gmail.com>",
    "license": "LGPL-3",
    "category": "Accounting/Localizations",
    "version": "19.0.1.0.0",
    "countries": ["ve"],
    "depends": [
        "l10n_ve",
        "account_reports",
    ],
    "data": [
        "data/res_currency_data.xml",
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
            "l10n_ve_dual_currency/static/src/components/aged_partner_balance/**/*",
        ],
    },
    "installable": True,
}
