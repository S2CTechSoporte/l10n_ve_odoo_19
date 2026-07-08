# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'S2C Reporte de Stock Picking',
    'summary': 'Ajustes al reporte de stockpicking para ajustarlo a los requerimientos del cliente',
    'category': 'Sale',
    'version': '19.0.1.0.0',
    'author': 'JGR AUTODIST, C.A.',
    'depends': ['stock', 'sale_stock', 's2c_product_package', 'mrp', 'stock_picking_batch'],
    'data': [
        'report/report_stockpicking_operations.xml',
        'report/report_deliveryslip.xml',
        'report/report_custom_deliveryslip.xml',
        'report/stockpicking_reports.xml',
        'report/report_stockpicking_templates.xml',
        'views/stock_picking_views.xml',
        'views/stock_move_line_views.xml',
        'views/stock_picking_batch_views.xml',
        'report/stock_picking_batch_report.xml',
        'report/transport_relation_report.xml',
    ],
    'demo': [
        'demo/s2c_stockpicking_report_demo.xml',
    ],
    'license': 'OPL-1',
    'application': True,
    'installable': True
}
