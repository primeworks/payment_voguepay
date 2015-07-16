# -*- coding: utf-'8' "-*-"
from hashlib import sha1
import logging
import urlparse
import urllib2
import json
from time import gmtime, strftime

from openerp.addons.payment.models.payment_acquirer import ValidationError
from openerp.addons.payment_buckaroo.controllers.main import BuckarooController
from openerp.osv import osv, fields
from openerp.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class AcquirerBuckaroo(osv.Model):
    _inherit = 'payment.acquirer'

    def _get_buckaroo_urls(self, cr, uid, environment, context=None):
        """ Buckaroo URLs
        """
        if environment == 'prod':
            return {
                'buckaroo_form_url': 'https://voguepay.com/pay/',
            }
        else:
            return {
                'buckaroo_form_url': 'https://voguepay.com/pay/',
            }

    def _get_providers(self, cr, uid, context=None):
        providers = super(AcquirerBuckaroo, self)._get_providers(cr, uid, context=context)
        providers.append(['buckaroo', 'Buckaroo'])
        return providers

    _columns = {
        'brq_websitekey': fields.char('Merchant ID', required_if_provider='buckaroo'),
        'brq_secretkey': fields.char('API Key', required_if_provider='buckaroo'),
    }

    def _buckaroo_generate_digital_sign(self, acquirer, inout, values):
        """ Generate the shasign for incoming or outgoing communications.

        :param browse acquirer: the payment.acquirer browse record. It should
                                have a shakey in shaky out
        :param string inout: 'in' (openerp contacting buckaroo) or 'out' (buckaroo
                             contacting openerp).
        :param dict values: transaction values

        :return string: shasign
        """
        assert inout in ('in', 'out')
        assert acquirer.provider == 'buckaroo'

        keys = "add_returndata Brq_amount Brq_culture Brq_currency Brq_invoicenumber Brq_return Brq_returncancel Brq_returnerror Brq_returnreject brq_test Brq_websitekey".split()

        def get_value(key):
            if values.get(key):
                return values[key]
            return ''

        values = dict(values or {})

        if inout == 'out':
            if 'BRQ_SIGNATURE' in values:
                del values['BRQ_SIGNATURE']
            items = sorted((k.upper(), v) for k, v in values.items())
            sign = ''.join('%s=%s' % (k, v) for k, v in items)
        else:
            sign = ''.join('%s=%s' % (k,get_value(k)) for k in keys)
        #Add the pre-shared secret key at the end of the signature
        sign = sign + acquirer.brq_secretkey
        if isinstance(sign, str):
            sign = urlparse.parse_qsl(sign)
        shasign = sha1(sign).hexdigest()
        return shasign


    def buckaroo_form_generate_values(self, cr, uid, id, partner_values, tx_values, context=None):
        base_url = self.pool['ir.config_parameter'].get_param(cr, uid, 'web.base.url')
        acquirer = self.browse(cr, uid, id, context=context)
        buckaroo_tx_values = dict(tx_values)
        buckaroo_tx_values.update({
            'Brq_websitekey': acquirer.brq_websitekey,
            'Brq_amount': tx_values['amount'],
            'Brq_currency': tx_values['currency'] and tx_values['currency'].name or '',
            'Brq_invoicenumber': tx_values['reference'],
            'brq_test': False if acquirer.environment == 'prod' else True,
            'Brq_return': '%s' % urlparse.urljoin(base_url, BuckarooController._return_url),
            'Brq_returncancel': '%s' % urlparse.urljoin(base_url, BuckarooController._cancel_url),
            'Brq_returnerror': '%s' % urlparse.urljoin(base_url, BuckarooController._exception_url),
            'Brq_returnreject': '%s' % urlparse.urljoin(base_url, BuckarooController._reject_url),
            'Brq_culture': (partner_values.get('lang') or 'en_US').replace('_', '-'),
        })
        if buckaroo_tx_values.get('return_url'):
            buckaroo_tx_values['add_returndata'] = {'return_url': '%s' % buckaroo_tx_values.pop('return_url')}
        else: 
            buckaroo_tx_values['add_returndata'] = ''
        buckaroo_tx_values['Brq_signature'] = self._buckaroo_generate_digital_sign(acquirer, 'in', buckaroo_tx_values)
        return partner_values, buckaroo_tx_values

    def buckaroo_get_form_action_url(self, cr, uid, id, context=None):
        acquirer = self.browse(cr, uid, id, context=context)
        return self._get_buckaroo_urls(cr, uid, acquirer.environment, context=context)['buckaroo_form_url']

class TxBuckaroo(osv.Model):
    _inherit = 'payment.transaction'

    # buckaroo status
    _buckaroo_valid_tx_status = ['Approved']
    _buckaroo_pending_tx_status = ['Pending']
    _buckaroo_cancel_tx_status = ['Disputed']
    _buckaroo_error_tx_status = ['Failed']
    _buckaroo_reject_tx_status = ['Disputed']

    _columns = {
         'buckaroo_txnid': fields.char('Transaction ID'),
    }
    

    # --------------------------------------------------
    # FORM RELATED METHODS
    # --------------------------------------------------

    def _buckaroo_form_get_tx_from_data(self, cr, uid, data, context=None):
        """ Given a data dict coming from buckaroo, verify it and find the related
        transaction record. """
        #Use transaction_id to pull in more info from VoguePay
        transaction_id = data.get('transaction_id')
        #transaction_id = '559f55426a93a'
        response = urllib2.urlopen('https://voguepay.com/?v_transaction_id=%s&type=json' % (transaction_id))
        myTx = json.load(response)

#        reference, pay_id, shasign = data.get('memo'), data.get('transaction_id'), data.get('merchant_ref')
        reference, pay_id, shasign = myTx['memo'], data.get('transaction_id'), myTx['merchant_ref']
        
        if not reference or not pay_id or not shasign:
            #        if not reference:
            error_msg = 'Buckaroo: received data with missing reference (%s) or pay_id (%s) or shashign (%s)' % (reference, pay_id, shasign)
            _logger.error(error_msg)
            raise ValidationError(error_msg)
#
        tx_ids = self.search(cr, uid, [('reference', '=', reference)], context=context)
        if not pay_id:
            error_msg = 'Buckaroo: received data for reference %s' % (reference)
            if not tx_ids:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.error(error_msg)
            raise ValidationError(error_msg)
        tx = self.pool['payment.transaction'].browse(cr, uid, tx_ids[0], context=context)

        #verify shasign
#        shasign_check = self.pool['payment.acquirer']._buckaroo_generate_digital_sign(tx.acquirer_id, 'out' ,data)
#        if shasign_check.upper() != shasign.upper():
#            error_msg = 'Buckaroo: invalid shasign, received %s, computed %s, for data %s' % (shasign, shasign_check, data)
#            _logger.error(error_msg)
#            raise ValidationError(error_msg)

        return tx

    def _buckaroo_form_get_invalid_parameters(self, cr, uid, tx, data, context=None):
        invalid_parameters = []

        if tx.acquirer_reference and data.get('transaction_id') != tx.acquirer_reference:
            invalid_parameters.append(('Transaction Id', data.get('transaction_id'), tx.acquirer_reference))
        # check what is buyed
        
        #Use transaction_id to pull in more info from VoguePay
        transaction_id = data.get('transaction_id')
        #transaction_id = '559f55426a93a'
        response = urllib2.urlopen('https://voguepay.com/?v_transaction_id=%s&type=json' % (transaction_id))
        myTx = json.load(response)
        

        if float_compare(float(myTx.get('total', '0.0')), tx.amount, 2) != 0:
            invalid_parameters.append(('Amount', data.get('total'), '%.2f' % tx.amount))
#        if data.get('BRQ_CURRENCY') != tx.currency_id.name:
#            invalid_parameters.append(('Currency', data.get('BRQ_CURRENCY'), tx.currency_id.name))

        return invalid_parameters

    def _buckaroo_form_validate(self, cr, uid, tx, data, context=None):
        
        #Use transaction_id to pull in more info from VoguePay
        transaction_id = data.get('transaction_id')
        #transaction_id = '559f55426a93a'
        response = urllib2.urlopen('https://voguepay.com/?v_transaction_id=%s&type=json' % (transaction_id))
        myTx = json.load(response)
        
        #Pull out the confirmations from the transaction_id
        status_code = myTx['status']
        if status_code in self._buckaroo_valid_tx_status:
            #        if data.get('transaction_id'):
            # Adding more detail to the final form
            _logger.info('Validated Paypal payment for tx %s: set as done' % (myTx['memo']))
            tx.write({
                'state': 'done',
                'buckaroo_txnid': data.get('transaction_id'),
                'date_validate': myTx['date'],
            })
            return True
        elif status_code in self._buckaroo_pending_tx_status:
            tx.write({
                'state': 'pending',
                'buckaroo_txnid': data.get('transaction_id'),
            })
            return True
        elif status_code in self._buckaroo_cancel_tx_status:
            tx.write({
                'state': 'cancel',
                'buckaroo_txnid': data.get('transaction_id'),
            })
            return True
        else:
            error = 'Buckaroo: feedback error'
            _logger.info(error)
            tx.write({
                'state': 'error',
                'state_message': error,
                'buckaroo_txnid': data.get('transaction_id'),
            })
            return False
