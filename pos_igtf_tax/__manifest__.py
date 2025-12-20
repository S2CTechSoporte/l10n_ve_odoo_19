# -*- coding: utf-8 -*-
{
    'name': 'Venezuela: POS IGTF',
    'version': '19.0.1.0.0',
    'author': 'Juan Córdoba',
    'company': 'Juan Córdoba',
    'maintainer': 'Juan Córdoba',
    'website': '',
    'category': 'Sales/Point of Sale',
    'summary': 'IGTF en el POS',
    'depends': ['point_of_sale','pos_show_dual_currency'],
    'data': [
        'views/inherited_views.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'pos_igtf_tax/static/src/scss/**/*',
            'pos_igtf_tax/static/src/xml/**/*',
            'pos_igtf_tax/static/src/js/**/*',
        ],
    },
    'license': 'LGPL-3',
}
