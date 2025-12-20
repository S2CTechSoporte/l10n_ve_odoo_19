# -*- coding: utf-8 -*-
import ast
import datetime
import io
import json
import logging
import math
import re
import base64
from ast import literal_eval
from collections import defaultdict
from functools import cmp_to_key

import markupsafe
from babel.dates import get_quarter_names
from dateutil.relativedelta import relativedelta

from odoo.addons.web.controllers.utils import clean_action
from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang, format_date
from odoo.tools.safe_eval import expr_eval, safe_eval
from odoo.models import check_method_name

import xlsxwriter

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    curr_currency_id = fields.Many2one('res.currency', string='Currency')
    
    def apply_change_curr_conversion(self, currency_id):
        report = self.env["account.report"].browse(self.id)
        currency = self.env["res.currency"].browse(currency_id)
        if report and currency:
            if report.curr_currency_id == currency:
                # si se selecciona la misma moneda, se desactiva el filtro 
                report.curr_currency_id = None
            else:
                report.curr_currency_id = currency
    
    def _init_options_date(self, options, previous_options=None):

        # active_currencies = self.env['res.currency'].search([('active', '=', True)])
        active_currencies = self.env['res.currency'].browse([self.env.company.currency_id.id, self.env.company.fcurrency_id.id])
        if len(active_currencies) < 2:
            # You need to activate more than one currency to access this report.
            options['curr_conversion'] = False
        else:
            options['curr_conversion'] = True           

        options['currencies'] = {
            str(currency_id.id): {
                'currency_id': currency_id.id,
                'currency_name': currency_id.name,
                'currency_selected': self.curr_currency_id.id == currency_id.id,

            } for currency_id in active_currencies
        }

        res = super()._init_options_date(options, previous_options=previous_options)
        return res
    
    def _get_options_domain(self, options, date_scope):
        domain = super()._get_options_domain(options, date_scope)

        currencies = options.get('currencies') or {}
        currency_selected = next(
            (vals.get('currency_id') for vals in currencies.values() if vals.get('currency_selected')),
            None,
        )
        if currency_selected:
            # filtra por moneda solo en los reportes de cuenta por pagar y cobrar
            cxc = self.env.ref('account_reports.aged_receivable_report').id
            cxp = self.env.ref('account_reports.aged_payable_report').id
            if self.id in (cxc, cxp):
                domain += [('currency_id', '=', currency_selected)]
        
        if options.get('account_ids'):
            domain += [('account_id', 'in', options['account_ids'])]
        return domain
    
    def _init_options_account_type(self, options, previous_options=None):
        res = super()._init_options_account_type(options, previous_options=previous_options)

        account_type = options.get('account_type')
        previous_account_ids = previous_options and previous_options.get('account_ids') or []

        selected_account_ids = [int(account) for account in previous_account_ids]
        selected_accounts = selected_account_ids and self.env['account.account'].with_context(active_test=False).search([('id', 'in', selected_account_ids)]) \
            or self.env['account.account'].search([
                ('company_ids', 'in', [self.env.company.id]),
                ('account_type', '=', account_type),
            ])
        options['selected_account_ids'] = selected_accounts.mapped('display_name')
        options['account_ids'] = selected_accounts.ids

        
        return res 


