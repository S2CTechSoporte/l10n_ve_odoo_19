# -*- coding: utf-8 -*-

# Part of Probuse Consulting Service Pvt Ltd. See LICENSE file for full copyright and licensing details.

{
    'name': 'Product/Material Internal Requisitions by Employees/Users',
    'version': '19.0.1.0.0',
    'price': 99.0,
    'currency': 'EUR',
    'license': 'Other proprietary',
    'summary': """This module allow your employees/users to create Internal Requisitions.""",
    'description': """
This module allow your employees/users to create Internal Requisitions. Employees can create requisitions for the products they need and send them for approval. Managers can approve or reject the requisitions and manage the inventory accordingly. This module helps to streamline the internal procurement process and improve communication between employees and managers regarding material needs.
    """,
    'author': 'S2C Technology',
    'images': ['static/description/img1.jpg'],
    # 'live_test_url': 'https://youtu.be/giqUttgLE9E',
    'live_test_url': 'https://youtu.be/Z4UzyTYiVvM',
    'category': 'Warehouse',
    'depends': [
                'stock',
                'hr',
                'analytic'
                ],
    'data':[
        'security/ir.model.access.csv',
        'security/multi_company_security.xml',
        'security/requisition_security.xml',
        'security/requisition_system_admin_implied.xml',
        #'data/requisition_sequence.xml',
        'data/employee_approval_template.xml',
        'data/confirm_template.xml',
        'report/requisition_report.xml',
        'views/requisition_view.xml',
        'views/hr_employee_view.xml',
        'views/stock_picking_view.xml',
    ],
    'installable' : True,
    'application' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
