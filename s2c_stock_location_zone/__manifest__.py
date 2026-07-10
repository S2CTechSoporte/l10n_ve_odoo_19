# -*- coding: utf-8 -*-
{
    'name': 'S2C Stock Location Zone',
    'summary': 'Adds destination zone fields to stock pickings',
    'category': 'Inventory',
    'version': '19.0.1.0.0',
    'author': 'S2C Technology',
    'license': 'OPL-1',
    'depends': ['stock', 'l10n_ve_dpt'],
    'data': [
        'views/stock_picking_views.xml',
        'views/stock_move_line_views.xml',
    ],
    'demo': [
        'demo/s2c_stock_location_zone_demo.xml',
    ],
    'installable': True,
    'application': True,
}