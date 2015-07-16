# -*- coding: utf-8 -*-

{
    'name': 'VoguePay Payment Acquirer',
    'category': 'Hidden',
    'summary': 'Payment Acquirer: VoguePay Implementation',
    'version': '1.0',
    'description': """VoguePay Payment Acquirer""",
    'author': 'Silicon Streets',
    'depends': ['payment'],
    'data': [
        'views/voguepay.xml',
        'views/payment_acquirer.xml',
        'data/voguepay.xml',
    ],
    'installable': True,
}
