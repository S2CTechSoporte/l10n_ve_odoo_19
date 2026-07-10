# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Campos adicionales en Empaque',
    'summary': 'Se agregan campos adicionales Litros por empaquetado y Peso por empaquetado',
    'description': """
        
    """,
    'category': 'Inventory',
    'version': '19.0.1.0.0',
    'author': 'S2C Technology',
    'depends': ['product', 'stock', 'stock_picking_batch', 'account', 'l10n_ve_dpt'],
    'data': [
        'views/product_template_view.xml',
        'views/product_product_stock_tree.xml',
        'views/view_stock_quant_tree_editable.xml',
        'views/view_picking_form.xml',
        'views/stock_picking_batch_views.xml',
        'views/product_packaging_quant.xml',
        'security/ir.model.access.csv'
    ],
    'demo': [
        'demo/s2c_product_package_demo.xml',
    ],
    "license": 'OPL-1',
    "auto_install": False,
    'application': True,
    'installable': True
}
