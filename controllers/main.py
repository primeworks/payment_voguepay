# -*- coding: utf-8 -*-
try:
    import simplejson as json
except ImportError:
    import json

import logging
import pprint
import werkzeug

from openerp import http, SUPERUSER_ID
from openerp.http import request

_logger = logging.getLogger(__name__)


class VoguePayController(http.Controller):
    _return_url = '/payment/voguepay/return'
    _cancel_url = '/payment/voguepay/cancel'
    _exception_url = '/payment/voguepay/error'
    _reject_url = '/payment/voguepay/reject'

    @http.route([
        '/payment/voguepay/return',
        '/payment/voguepay/cancel',
        '/payment/voguepay/error',
        '/payment/voguepay/reject',
    ], type='http', auth='none')
    def voguepay_return(self, **post):
        """ VoguePay."""
        _logger.info('VoguePay: entering form_feedback with post data %s', pprint.pformat(post))  # debug
        request.registry['payment.transaction'].form_feedback(request.cr, SUPERUSER_ID, post, 'voguepay', context=request.context)
        return_url = post.pop('return_url', '')
        if not return_url:
            data ='' + post.pop('ADD_RETURNDATA', '{}').replace("'", "\"")
            custom = json.loads(data)
            return_url = custom.pop('return_url', '/')
        return werkzeug.utils.redirect(return_url)
