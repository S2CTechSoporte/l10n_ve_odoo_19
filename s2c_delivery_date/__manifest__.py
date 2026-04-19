# -*- coding: utf-8 -*-
{
    "name": "S2C Delivery Date",
    "summary": "Permite recalcular fecha de vencimiento de factura a partir de la fecha de entrega",
    "version": "19.0.1.1.0",
    "author": "S2C Technology, C.A.",
    "category": "Accounting",
    "license": "AGPL-3",
    "depends": ["account", "account_reports"],
    "data": [
        'views/move_form_view.xml',
        'data/account_aged_receivable_report.xml',
    ],
    "demo": [
        'demo/s2c_delivery_date_demo.xml',
    ],
    "installable": True,
    "application": True
}
