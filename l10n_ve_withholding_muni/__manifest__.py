# -*- coding: utf-8 -*-


{
        'name': 'Municipal Taxes for Venezuela Localization',
        'version': '19.0.1.0.0',
        'author': 'S2C Technology',
        'maintainer': 'Juan Córdoba <jgcordobac@gmail.com>',
        'description': 'Municipal Taxes',
        'category': 'Accounting/Accounting',
        'website': '',
        'images': [],
        # 'depends': [
        #     'account',
        #     'account_accountant',
        #     'base',
        #     'locv_withholding_iva',
        #     'l10n_ve_dpt',
        #     'multi_schema'
        #     ],
        'depends': [
            'l10n_ve_dpt',
            'l10n_ve_full'
        ],
        'data': [
            'security/ir.model.access.csv',
            'data/muni.wh.concept.csv',
            #'data/seq_muni_tax_data.xml',
            'data/period.month.csv',
            'data/period.year.csv',
            'views/account_move_views.xml',
            'views/res_partner_views.xml',
            'views/municipality_tax_views.xml',
            'report/report_municipal_tax.xml',
            # 'views/res_company_views.xml',
            'views/res_config_settings.xml'
            ],
        'installable': True,
        'application': True,
        'auto_install': False,
        'license': 'LGPL-3',
        
        }
