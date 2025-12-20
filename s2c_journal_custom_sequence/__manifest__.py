# -*- coding: utf-8 -*-
{
    'name': "Journal Custom Sequence",

    'summary': """
        Permite compartir secuencias entre distintos diarios""",

    'description': """
        
    """,

    'author': "S2C Technology",
    'website': "",

    'category': 'account',
    'version': '19.0.1.0.0',

    'depends': ['account', 's2c_number_final_sequence', 'l10n_ve_full'],

    'data': [
        'views/view_account_journal_form.xml'
    ],
    'application': True,
    'license': 'LGPL-3',
}
