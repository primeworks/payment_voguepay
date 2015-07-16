# -*- coding: utf-8 -*-
from openerp import http

# class PaymentVoguepay(http.Controller):
#     @http.route('/payment_voguepay/payment_voguepay/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/payment_voguepay/payment_voguepay/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('payment_voguepay.listing', {
#             'root': '/payment_voguepay/payment_voguepay',
#             'objects': http.request.env['payment_voguepay.payment_voguepay'].search([]),
#         })

#     @http.route('/payment_voguepay/payment_voguepay/objects/<model("payment_voguepay.payment_voguepay"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('payment_voguepay.object', {
#             'object': obj
#         })