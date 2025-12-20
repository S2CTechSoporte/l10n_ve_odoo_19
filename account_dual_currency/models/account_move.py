# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    float_compare,
    float_is_zero,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)
import json


class AccountMove(models.Model):
    _inherit = 'account.move'

    fcurrency_id = fields.Many2one("res.currency",
                                      string="Moneda Dual Ref.",
                                      default=lambda self: self.env.company.fcurrency_id )
    invoice_date = fields.Date(
        default=lambda self: fields.Date.context_today(self)
    )

    acuerdo_moneda = fields.Boolean(string="Acuerdo de Factura Bs.", default=False)

    tax_today = fields.Float(string="Tasa",
                compute="_compute_tax_today",
                inverse="_set_tax_today",
                store=True,
                digits='Dual_Currency_rate')
                             

    edit_trm = fields.Boolean(string="Editar tasa", default=False)

    name_rate = fields.Char(store=True, readonly=True, compute='_name_ref')
    amount_untaxed_fcurrency = fields.Monetary(
        currency_field='fcurrency_id',
        string="Base imponible ¤",
        store=True,
        compute="_amount_all_fcurrency",
    )
    amount_tax_fcurrency = fields.Monetary(
        currency_field='fcurrency_id',
        string="Impuestos ¤",
        store=True,
        readonly=True,
        compute="_amount_all_fcurrency",
    )
    amount_total_fcurrency = fields.Monetary(
        currency_field='fcurrency_id',
        string='Total ¤',
        store=True,
        readonly=True,
        compute='_amount_all_fcurrency',
        tracking=True,
    )

    amount_residual_fcurrency = fields.Monetary(
        currency_field='fcurrency_id',
        compute='_compute_amount',
        string='Adeudado ¤',
        readonly=True,
        store=True,
    )
    invoice_payments_widget_fcurrency = fields.Binary(groups="account.group_account_invoice,account.group_account_readonly",
                                              compute='_compute_payments_widget_reconciled_info_fcurrency')

    amount_untaxed_bs = fields.Monetary(currency_field='company_currency_id', string="Base imponible Bs.", store=True,
                                        compute="_amount_all_fcurrency")
    amount_tax_bs = fields.Monetary(currency_field='company_currency_id', string="Impuestos Bs.", store=True,
                                    readonly=True)
    amount_total_bs = fields.Monetary(currency_field='company_currency_id', string='Total Bs.', store=True,
                                      readonly=True,
                                      compute='_amount_all_fcurrency')

    amount_total_signed_fcurrency = fields.Monetary(
        string='Total Signed ¤',
        compute='_compute_amount', store=True, readonly=True,
        currency_field='fcurrency_id',
    )

    invoice_payments_widget_bs = fields.Text(groups="account.group_account_invoice")

    same_currency = fields.Boolean(string="Mismo tipo de moneda", compute='_same_currency')

    asset_remaining_value_ref = fields.Monetary(currency_field='fcurrency_id', string='Valor depreciable Ref.', copy=False)
    asset_depreciated_value_ref = fields.Monetary(currency_field='fcurrency_id', string='Depreciación Acu. Ref.', copy=False)

    @api.depends('currency_id')
    def _same_currency(self):
        self.same_currency = self.currency_id == self.env.company.currency_id

    @api.depends('invoice_date', 'date')
    def _compute_tax_today(self):
        for rec in self:
            fcurrency_id = self.env.company.fcurrency_id
            
            if rec.move_type == 'entry':
                date = rec.date or fields.Date.context_today(self)
            else:
                date = rec.invoice_date or fields.Date.context_today(self)

            rates = fcurrency_id._get_rates( rec.company_id, date)
            if rates:
                if fcurrency_id != self.env.ref('base.USD'):
                    tax_today = round(rates[fcurrency_id.id], 4)
                else:
                    tax_today = round(1 / rates[fcurrency_id.id], 4)
            rec.tax_today = tax_today

    def _set_tax_today(self):
        pass
    
    @api.onchange('edit_trm')
    def _onchange_edit_trm(self):
        for rec in self:
            if not rec.edit_trm: 
                rec._compute_tax_today()

    @api.depends('fcurrency_id')
    def _name_ref(self):
        for record in self:
            record.name_rate = record.fcurrency_id.currency_unit_label
    
    @api.depends(
        'tax_totals',
        'fcurrency_id',
        'currency_id',
        'tax_today')
    def _amount_all_fcurrency(self):
        for record in self:
            company = record.company_id
            record.amount_untaxed_fcurrency = company.currency_id.with_context(
                {'edit_trm': record.edit_trm, 'tax_today': record.tax_today}
                )._convert(record.amount_untaxed, record.fcurrency_id, company, record.date, False)
            
            record.amount_tax_fcurrency = company.currency_id.with_context(
                {'edit_trm': record.edit_trm, 'tax_today': record.tax_today}
                )._convert(record.amount_tax, record.fcurrency_id, company, record.date, False)
            
            record.amount_total_fcurrency = company.currency_id.with_context(
                {'edit_trm': record.edit_trm, 'tax_today': record.tax_today}
                )._convert(record.amount_total, record.fcurrency_id, company, record.date,False)


    @api.depends('move_type', 'line_ids.amount_residual_fcurrency')
    def _compute_payments_widget_reconciled_info_fcurrency(self):
        for move in self:
            payments_widget_vals = {'title': _('Less Payment'), 'outstanding': False, 'content': []}
            total_pagado = 0
            if move.state == 'posted' and move.is_invoice(include_receipts=True):
                reconciled_vals = []
                reconciled_partials = move._get_all_reconciled_invoice_partials_fcurrency()

                for reconciled_partial in reconciled_partials:
                    counterpart_line = reconciled_partial['aml']
                    if counterpart_line.move_id.ref:
                        reconciliation_ref = '%s (%s)' % (counterpart_line.move_id.name, counterpart_line.move_id.ref)
                    else:
                        reconciliation_ref = counterpart_line.move_id.name
                    if counterpart_line.amount_currency and counterpart_line.currency_id != counterpart_line.company_id.currency_id:
                        foreign_currency = counterpart_line.currency_id
                    else:
                        foreign_currency = False
                    total_pagado = total_pagado + float(reconciled_partial['amount'])
                    reconciled_vals.append({
                        'name': counterpart_line.name,
                        'journal_name': counterpart_line.journal_id.name,
                        'amount': reconciled_partial['amount'],
                        'currency_id': move.company_id.fcurrency_id.id if move.company_id.fcurrency_id else
                        move.company_id.currency_id.id,
                        'date': counterpart_line.date,
                        'partial_id': reconciled_partial['partial_id'],
                        'account_payment_id': counterpart_line.payment_id.id,
                        'payment_method_name': counterpart_line.payment_id.payment_method_line_id.name,
                        'move_id': counterpart_line.move_id.id,
                        'ref': reconciliation_ref,
                        # these are necessary for the views to change depending on the values
                        'is_exchange': reconciled_partial['is_exchange'],
                        'amount_company_currency': formatLang(self.env, abs(counterpart_line.balance_fcurrency),
                                                              currency_obj=counterpart_line.company_id.fcurrency_id),
                        'amount_foreign_currency': foreign_currency and formatLang(self.env,
                                                                                   abs(counterpart_line.amount_currency),
                                                                                   currency_obj=foreign_currency)
                    })
                payments_widget_vals['content'] = reconciled_vals

            if payments_widget_vals['content']:
                move.invoice_payments_widget_fcurrency = payments_widget_vals
                if total_pagado < move.amount_total_fcurrency:
                    move.amount_residual_fcurrency = move.amount_total_fcurrency - total_pagado
                else:
                    move.amount_residual_fcurrency = 0
            else:
                move.amount_residual_fcurrency = move.amount_total_fcurrency
                move.invoice_payments_widget_fcurrency = False
            
           
            if move.currency_id == move.fcurrency_id:
                move.amount_residual_fcurrency = move.amount_residual
            else:
                if move.tax_today > 0:
                    move.amount_residual_fcurrency = move.currency_id.with_context(
                                    {'edit_trm': move.edit_trm, 'tax_today': move.tax_today}
                                    )._convert(move.amount_residual, move.fcurrency_id, move.company_id , move.date, False)

    @api.depends('move_type', 'line_ids.amount_residual_fcurrency')
    def _compute_payments_widget_reconciled_info_bs(self):
        for move in self:
            if move.state != 'posted' or not move.is_invoice(include_receipts=True):
                move.invoice_payments_widget_bs = json.dumps(False)
                continue
            reconciled_vals = move._get_reconciled_info_JSON_values_bs()
            if reconciled_vals:
                info = {
                    'title': _('Less Payment'),
                    'outstanding': False,
                    'content': reconciled_vals,
                }
                move.invoice_payments_widget_bs = json.dumps(info, default=date_utils.json_default)
            else:
                move.invoice_payments_widget_bs = json.dumps(False)

    def _get_reconciled_info_JSON_values_bs(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id

            counterpart_line = counterpart_lines.filtered(lambda line: line not in self.line_ids)

            if counterpart_line.credit > 0:
                amount = counterpart_line.credit
            else:
                amount = counterpart_line.debit

            ref = counterpart_line.move_id.name
            if counterpart_line.move_id.ref:
                ref += ' (' + counterpart_line.move_id.ref + ')'

            reconciled_vals.append({
                'name': counterpart_line.name,
                'journal_name': counterpart_line.journal_id.name,
                'amount': partial.amount,
                'currency': self.fcurrency_id.symbol,
                'digits': [69, 2],
                'position': self.fcurrency_id.position,
                'date': counterpart_line.date,
                'payment_id': counterpart_line.id,
                'account_payment_id': counterpart_line.payment_id.id,
                'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                'move_id': counterpart_line.move_id.id,
                'ref': ref,
            })
        # print(reconciled_vals)
        return reconciled_vals

    def _get_all_reconciled_invoice_partials_fcurrency(self):
        self.ensure_one()
        reconciled_lines = self.line_ids.filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))
        if not reconciled_lines:
            return {}

        query = '''
            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_fcurrency AS amount,
                part.credit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.debit_move_id IN %s

            UNION ALL

            SELECT
                part.id,
                part.exchange_move_id,
                part.amount_fcurrency AS amount,
                part.debit_move_id AS counterpart_line_id
            FROM account_partial_reconcile part
            WHERE part.credit_move_id IN %s
        '''
        self._cr.execute(query, [tuple(reconciled_lines.ids)] * 2)

        partial_values_list = []
        counterpart_line_ids = set()
        exchange_move_ids = set()
        for values in self._cr.dictfetchall():
            partial_values_list.append({
                'aml_id': values['counterpart_line_id'],
                'partial_id': values['id'],
                'amount': values['amount'],
                'currency': self.currency_id,
            })
            counterpart_line_ids.add(values['counterpart_line_id'])
            if values['exchange_move_id']:
                exchange_move_ids.add(values['exchange_move_id'])

        if exchange_move_ids:
            query = '''
                SELECT
                    part.id,
                    part.credit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line credit_line ON credit_line.id = part.credit_move_id
                WHERE credit_line.move_id IN %s AND part.debit_move_id IN %s

                UNION ALL

                SELECT
                    part.id,
                    part.debit_move_id AS counterpart_line_id
                FROM account_partial_reconcile part
                JOIN account_move_line debit_line ON debit_line.id = part.debit_move_id
                WHERE debit_line.move_id IN %s AND part.credit_move_id IN %s
            '''
            self._cr.execute(query, [tuple(exchange_move_ids), tuple(counterpart_line_ids)] * 2)

            for values in self._cr.dictfetchall():
                counterpart_line_ids.add(values['counterpart_line_id'])
                partial_values_list.append({
                    'aml_id': values['counterpart_line_id'],
                    'partial_id': values['id'],
                    'currency': self.company_id.currency_id,
                })

        counterpart_lines = {x.id: x for x in self.env['account.move.line'].browse(counterpart_line_ids)}
        for partial_values in partial_values_list:
            partial_values['aml'] = counterpart_lines[partial_values['aml_id']]
            partial_values['is_exchange'] = partial_values['aml'].move_id.id in exchange_move_ids
            if partial_values['is_exchange']:
                partial_values['amount'] = abs(partial_values['aml'].balance_fcurrency)

        return partial_values_list

    def js_assign_outstanding_line(self, line_id):
        ''' Called by the 'payment' widget to reconcile a suggested journal item to the present
        invoice.

        :param line_id: The id of the line to reconcile with the current invoice.
        '''
        self.ensure_one()
        lines = self.env['account.move.line'].browse(line_id)
        l = self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
        if abs(lines[0].amount_residual) == 0 and abs(lines[0].amount_residual_fcurrency) > 0:
            if l.full_reconcile_id:
                l.full_reconcile_id.unlink()
            partial = self.env['account.partial.reconcile'].create([{
                'amount': 0,
                'amount_fcurrency': l.move_id.amount_residual_fcurrency if abs(
                    lines[0].amount_residual_fcurrency) > l.move_id.amount_residual_fcurrency else abs(
                    lines[0].amount_residual_fcurrency),
                'debit_amount_currency': 0,
                'credit_amount_currency': 0,
                'debit_move_id': l.id,
                'credit_move_id': line_id,
            }])
            p = (lines + l).reconcile()
            (lines + l)._compute_amount_residual_fcurrency()
            return p
        else:
            results = (lines + l).reconcile()
            if type(results) is dict and 'partials' in results:
                if results['partials'].amount_fcurrency == 0:
                    monto_fcurrency = 0
                    if abs(lines[0].amount_residual_fcurrency) > 0:

                        # print("1")
                        if abs(lines[0].amount_residual_fcurrency) > self.amount_residual_fcurrency:
                            # print("2")
                            monto_fcurrency = self.amount_residual_fcurrency
                        else:
                            # print("3")
                            monto_fcurrency = abs(lines[0].amount_residual_fcurrency)
                    results['partials'].write({'amount_fcurrency': monto_fcurrency})
                    lines[0]._compute_amount_residual_fcurrency()
            return results

    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids \
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|','|', ('amount_residual', '!=', 0.0), ('amount_residual_fcurrency', '!=', 0.0),('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):
                if line.debit == 0 and line.credit == 0 and not line.full_reconcile_id:
                    if abs(line.amount_residual_fcurrency) > 0:
                        payments_widget_vals['content'].append({
                            'journal_name': line.ref or line.move_id.name,
                            'amount': 0,
                            'amount_fcurrency': abs(line.amount_residual_fcurrency),
                            'currency_id': move.currency_id.id,
                            'fcurrency_id': move.fcurrency_id.id,
                            'id': line.id,
                            'move_id': line.move_id.id,
                            'date': fields.Date.to_string(line.date),
                            'account_payment_id': line.payment_id.id,
                        })
                        continue
                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                    amount_fcurrency = abs(line.amount_residual_fcurrency)
                else:
                    # Different foreign currencies.
                    amount = line.company_currency_id.with_context({'edit_trm': move.edit_trm, 'tax_today': move.tax_today})._convert(
                        abs(line.amount_residual),
                        move.currency_id,
                        move.company_id,
                        line.date,
                    )
                    amount_fcurrency = abs(line.amount_residual_fcurrency)

                if move.currency_id.is_zero(amount) and amount_fcurrency == 0:
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'amount_fcurrency': amount_fcurrency,
                    'currency_id': move.currency_id.id,
                    'fcurrency_id': move.fcurrency_id.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                })

            if not payments_widget_vals['content']:
                continue
            #print(payments_widget_vals)
            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True

    @api.model
    def _prepare_move_for_asset_depreciation(self, vals):
        move_vals = super(AccountMove, self)._prepare_move_for_asset_depreciation(vals)
        asset_id = vals.get('asset_id')
        move_vals['tax_today'] = asset_id.tax_today
        move_vals['fcurrency_id'] = asset_id.fcurrency_id.id
        #move_vals['asset_remaining_value_ref'] = move_vals['asset_remaining_value'] / asset_id.tax_today
        #move_vals['asset_depreciated_value_ref'] = move_vals['asset_depreciated_value'] / asset_id.tax_today
        return move_vals
    

    def _build_credit_warning_message(self, record, updated_credit):
        ''' Build the warning message that will be displayed in a yellow banner on top of the current record
            if the partner exceeds a credit limit (set on the company or the partner itself).
            :param record:                  The record where the warning will appear (Invoice, Sales Order...).
            :param updated_credit (float):  The partner's updated credit limit including the current record.
            :return (str):                  The warning message to be showed.
        '''
        partner_id = record.partner_id.commercial_partner_id
        if not partner_id.credit_limit or updated_credit <= partner_id.credit_limit:
            return ''
        msg = _('%s alcanzó su límite de crédito de: %s\nImporte total adeudado ',
                partner_id.name,
                #formatLang(self.env, partner_id.credit_limit, currency_obj=record.company_id.currency_id))
                formatLang(self.env, partner_id.credit_limit, currency_obj=record.partner_id.commercial_partner_id.credit_limit_currency))
        
        date = None
        if 'date_order' in record._fields:
            date = record.date_order
        elif 'invoice_date' in record._fields:
            date = record.date
 

        credit = record.company_id.currency_id.with_context({'edit_trm': record.edit_trm, 'tax_today': record.tax_today})._convert(
                partner_id.credit,
                partner_id.credit_limit_currency,
                record.company_id,
                date #record.date_order
                )

        if updated_credit > credit: #partner_id.credit:
            msg += _('(incluyendo este documento) ')
        #msg += ': %s' % formatLang(self.env, updated_credit, currency_obj=record.company_id.currency_id)
        msg += ': %s' % formatLang(self.env, updated_credit, currency_obj=record.partner_id.commercial_partner_id.credit_limit_currency)
        return msg