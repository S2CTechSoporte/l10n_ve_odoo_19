{
    'name': 'S2C SENIAT Regulations',
    'version': '19.0.1.0.0',
    'author': 'S2C Technology',
    'category': 'Accounting',
    'summary': 'Custom regulations for SENIAT',
    'license': 'LGPL-3',
    'depends': ['account', 'sale', 'onboarding'],
    'data': [
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/onboarding_alert.xml',
        'views/onboarding_container_inherit.xml',
    ],
    'installable': True,
    'application': False,
}
