# -*- coding: utf-8 -*-
{
    'name': "Venezuela: Account Dual Currency",
    'version': '19.0.1.0.0',
    'category' : 'Account',
    'license': 'Other proprietary',
    'summary': """Esta aplicación permite manejar dualidad de moneda en Contabilidad.""",
    'author': 'Juan Córdoba',
    'company': 'Juan Córdoba',
    'maintainer': 'Juan Córdoba',
    'website': '',
    'description': """
    
        - Mantener como moneda principal Bs y $ como secundaria.
        - Facturas en Bs pero manteniendo deuda en $.
        - Tasa individual para cada Factura de Cliente y Proveedor.
        - Tasa individual para Asientos contables.
        - Visualización de Débito y Crédito en ambas monedas en los apuntes contables.
        - Conciliación total o parcial de $ y Bs en facturas.
        - Registro de pagos en facturas con tasa diferente a la factura.
        - Registro de anticipos en el módulo de Pagos de Odoo, manteniendo saldo a favor en $ y Bs.
        - Informe de seguimiento en $ y Bs a la tasa actual.
        - Reportes contables en $ (Vencidas por Pagar, Vencidas por Cobrar y Libro mayor de empresas)
        - Valoración de inventario en $ y Bs a la tasa actual

    """,
    'depends': [
                'base','l10n_ve_full','account','account_reports','account_followup','web',
                'stock',
                'stock_account','account_accountant','analytic','stock_landed_costs','account_debit_note','mail',
                'account_reports_cash_basis', 'account_asset'
                ],
    'data':[
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        'views/res_currency.xml',
        'views/res_config_settings.xml',
        'views/account_move_view.xml',
        'views/account_move_line.xml',
        'views/search_template_view.xml',
        'wizard/account_payment_register.xml',
        'views/account_payment.xml',
        'views/product_template.xml',
        'views/stock_landed_cost.xml',
        'views/account_journal_dashboard.xml',
        'data/decimal_precision.xml',
        'data/cron.xml',
        'data/channel.xml',
        'data/aged_partner_balance.xml',
        'data/profit_and_loss.xml',
        'data/balance_sheet.xml',
        'views/effective_date_change.xml',
        'views/product_template_attribute_value.xml',
        'views/account_asset.xml',
        'views/res_partner.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'account_dual_currency/static/src/xml/**/*',
            'account_dual_currency/static/src/js/**/*',
            'account_dual_currency/static/src/components/**/*'
        ],
    },
    'images': [
        'static/description/thumbnail.png',
    ],
    'live_test_url': 'https://localhost:8072/web/login',
    "price": 2990,
    "currency": "USD",
    'installable' : True,
    'application' : False,
}

