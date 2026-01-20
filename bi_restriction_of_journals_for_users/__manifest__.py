# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'User Journal Restrictions',
    'version': '19.0.0.0',
    'category': 'Accounting',
    'summary': 'Restrict journal user access account journal restriction journal restriction for users restrict journal security journal restricted user journal restrictions accounting journal restriction users journal restriction user wise journal restrictions for users',
    "description": """
       
        User Journal Restrictions Odoo App helps users to restricting the journals for particular users. User have access to restrict journals and select allowed journals for that specific user. User can visible only allowed journals and visible only allowed users in specific journal. User can visible or use only allowed journal in payment.

    """,
    'author': 'BROWSEINFO',
    "price": 15,
    "currency": 'EUR',
    'website': "https://www.browseinfo.com/demo-request?app=bi_restriction_of_journals_for_users&version=19&edition=Community",
    'depends': ['base', 'sale_management', 'account', 'stock', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'security/restrict_journal.xml',
        'views/journals_for_users.xml',
    ],
    'license':'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url':"https://www.browseinfo.com/demo-request?app=bi_restriction_of_journals_for_users&version=19&edition=Community",
    "images":['static/description/User-Journal-Restrictions-Banner.gif'],
}
