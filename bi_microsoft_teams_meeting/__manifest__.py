# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Odoo Microsoft Teams Connector | Microsoft Teams Integration with Odoo | Microsoft Teams Odoo Bridge',
    'version': '19.0.0.0',
    'category': 'Extra Tools',
    'summary': 'Microsoft teams odoo integration msteam connector ms team connector microsoft meeting integration with odoo activity to Microsoft Teams Bidirectional sync Microsoft Teams calendar sync meeting with odoo export meeting from odoo to ms team task sync Teams',
    'description': """Odoo Microsoft Teams Connector enables seamless collaboration by integrating Odoo with Microsoft Teams, allowing users to streamline communication, project coordination, and workflow management across both platforms. This powerful bridge ensures real-time synchronization between Odoo records and Teams conversations, facilitating instant updates, notifications, and task sharing within your organization’s preferred communication environment. By connecting the business logic and data of Odoo with the collaborative capabilities of Microsoft Teams, companies can enhance productivity, improve team engagement, and ensure a more connected and agile operational ecosystem without switching between platforms.""",
    "price": 29,
    "currency": 'EUR',
    "author": "BROWSEINFO",
    'website': 'https://www.browseinfo.com/demo-request?app=bi_microsoft_teams_meeting&version=18&edition=Community',
    'depends': ['base', 'calendar'],
    'data': [
        'data/ir_cron.xml',
        'views/view_calendar_event_form.xml',
        'views/res_users_views.xml',
    ],
    'license':'OPL-1',
    'installable': True,
    'auto_install': False,
    "live_test_url": 'https://www.browseinfo.com/demo-request?app=bi_microsoft_teams_meeting&version=18&edition=Community',
    "images": ["static/description/Banner.gif"],
}
