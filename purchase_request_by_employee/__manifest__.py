# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Purchase Request By Employee',
    'version' : '19.0.1.0.0',
    'author':'S2C Technology',
    'category': 'purchase',
    'maintainer': 'Craftsync Technologies',
    'summary': """Enable purchase Requisition by employee and user. Create Purchase Requisition.""",
    'website': 'https://www.craftsync.com/',
    'license': 'OPL-1',
    'support':'info@craftsync.com',
    'depends' : ['purchase','hr'],
    'data': [
        'security/group_security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/purchase_request.xml',
        'views/po.xml',
        'views/purchase_request_stage_view.xml'
    ],
    
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/main_screen.png'],
    'price': 19.99,
    'currency': 'USD',

}
