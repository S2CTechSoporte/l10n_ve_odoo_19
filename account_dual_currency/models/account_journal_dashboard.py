import ast
from babel.dates import format_datetime, format_date
from collections import defaultdict
from datetime import datetime, timedelta
import json
import random

from odoo import models, api, _, fields
from odoo.exceptions import UserError
from odoo.release import version
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools.misc import formatLang, format_date as odoo_format_date, get_lang

def group_by_journal(vals_list):
    res = defaultdict(list)
    for vals in vals_list:
        res[vals['journal_id']].append(vals)
    return res

class AccountJournal(models.Model):
    _inherit = "account.journal"
    
    def _fill_sale_purchase_dashboard_data(self, dashboard_data):

        super(AccountJournal, self)._fill_sale_purchase_dashboard_data(dashboard_data)

        for key, value in dashboard_data.items():

            journal = self.env['account.journal'].browse(key).exists()
            amount_draft = 0.0
            amount_waiting = 0.0
            amount_late = 0.0

            if journal.type == 'sale':
                draft_domain=[
                    ('company_id', 'in', self.env.companies.ids),
                    ('journal_id', '=', key),
                    ('state', '=', 'draft'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('move_type', 'in', self.env['account.move'].get_invoice_types(include_receipts=True)),
                ]
                waiting_domain=[
                    ('company_id', 'in', self.env.companies.ids),
                    ('journal_id', '=', key),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('move_type', 'in', self.env['account.move'].get_invoice_types(include_receipts=True)),
                ]

                late_domain=[
                    ('company_id', 'in', self.env.companies.ids),
                    ('journal_id', '=', key),
                    ('invoice_date_due', '<', fields.Date.context_today(self)),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('move_type', 'in', self.env['account.move'].get_invoice_types(include_receipts=True)),
                ]

                amount_draft = sum(self.env['account.move'].search(draft_domain).mapped('amount_total_fcurrency'))
                amount_waiting = sum(self.env['account.move'].search(waiting_domain).mapped('amount_total_fcurrency'))
                amount_late = sum(self.env['account.move'].search(late_domain).mapped('amount_total_fcurrency'))
            
            if journal.type == 'purchase':
                draft_domain=[
                    ('company_id', 'in', self.env.companies.ids),
                    ('journal_id', '=', key),
                    ('state', '=', 'draft'),
                    ('payment_state', 'in', ('not_paid', 'partial')),
                    ('move_type', 'in', self.env['account.move'].get_invoice_types(include_receipts=True)),
                ]
                waiting_domain=[
                    ('company_id', 'in', self.env.companies.ids),
                    ('journal_id', '=', key),
                    ('move_id.payment_state', 'in', ('not_paid', 'partial')),
                    ('date_maturity', '!=', False),
                    ('amount_residual', '<', 0),
                    ('parent_state', '=', 'posted'),
                    ('journal_id.type', '=', 'purchase'),
                ]
                late_domain=[
                    ('company_id', 'in', self.env.companies.ids),
                    ('journal_id', '=', key),
                    ('move_id.payment_state', 'in', ('not_paid', 'partial')),
                    ('date_maturity', '<', fields.Date.context_today(self)),
                    ('amount_residual', '<', 0),
                    ('parent_state', '=', 'posted'),
                    ('journal_id.type', '=', 'purchase'),
                ]

                amount_draft = sum(self.env['account.move'].search(draft_domain).mapped('amount_total_fcurrency'))
                amount_waiting = abs(sum(self.env['account.move.line'].search(waiting_domain).mapped('amount_residual_fcurrency')))
                amount_late = abs(sum(self.env['account.move.line'].search(late_domain).mapped('amount_residual_fcurrency')))
                

            symbol = self.env.company.fcurrency_id.symbol
            dashboard_data[key].update(
                {
                    'sum_draft_fcurrency': f'{symbol}\xa0{amount_draft:.2f}',
                    'sum_waiting_fcurrency': f'{symbol}\xa0{amount_waiting:.2f}',
                    'sum_late_fcurrency': f'{symbol}\xa0{amount_late:.2f}',
                }
            )


    #     """Populate all sale and purchase journal's data dict with relevant information for the kanban card."""
    #     sale_purchase_journals = self.filtered(lambda journal: journal.type in ('sale', 'purchase'))
    #     purchase_journals = self.filtered(lambda journal: journal.type == 'purchase')
    #     sale_journals = self.filtered(lambda journal: journal.type == 'sale')
    #     if not sale_purchase_journals:
    #         return
        
    #     bills_field_list = [
    #         "account_move.journal_id",
    #         "(CASE WHEN account_move.move_type IN ('out_refund', 'in_refund') THEN -1 ELSE 1 END) * account_move.amount_total_fcurrency AS amount_total",
    #         "account_move.amount_total_fcurrency AS amount_total_company",
    #         "account_move.fcurrency_id AS currency",
    #         "account_move.move_type",
    #         "account_move.invoice_date",
    #         "account_move.company_id",
    #     ]
        
        
            
    #     payment_field_list = [
    #         "account_move_line.journal_id",
    #         "account_move_line.move_id",
    #         "-account_move_line.amount_residual AS amount_total_company",
    #     ]
    #     # DRAFTS
    #     query, params = sale_purchase_journals._get_draft_bills_query().select(*bills_field_list)
    #     self.env.cr.execute(query, params)
    #     query_results_drafts = group_by_journal(self.env.cr.dictfetchall())

    #     # WAITING BILLS AND PAYMENTS
    #     query_results_to_pay = {}
    #     if purchase_journals:
    #         query, params = purchase_journals._get_open_payments_query().select(*payment_field_list)
    #         self.env.cr.execute(query, params)
    #         query_results_payments_to_pay = group_by_journal(self.env.cr.dictfetchall())
    #         for journal in purchase_journals:
    #             query_results_to_pay[journal.id] = query_results_payments_to_pay[journal.id]
    #     if sale_journals:
    #         query, params = sale_journals._get_open_bills_to_pay_query().select(*bills_field_list)
    #         self.env.cr.execute(query, params)
    #         query_results_bills_to_pay = group_by_journal(self.env.cr.dictfetchall())
    #         for journal in sale_journals:
    #             query_results_to_pay[journal.id] = query_results_bills_to_pay[journal.id]

    #     # LATE BILLS AND PAYMENTS
    #     late_query_results = {}
    #     if purchase_journals:
    #         query, params = purchase_journals._get_late_payment_query().select(*payment_field_list)
    #         self.env.cr.execute(query, params)
    #         late_payments_query_results = group_by_journal(self.env.cr.dictfetchall())
    #         for journal in purchase_journals:
    #             late_query_results[journal.id] = late_payments_query_results[journal.id]
    #     if sale_journals:
    #         query, params = sale_journals._get_late_bills_query().select(*bills_field_list)
    #         self.env.cr.execute(query, params)
    #         late_bills_query_results = group_by_journal(self.env.cr.dictfetchall())
    #         for journal in sale_journals:
    #             late_query_results[journal.id] = late_bills_query_results[journal.id]

    #     to_check_vals = {
    #         journal.id: (amount_total_signed_sum, count)
    #         for journal, amount_total_signed_sum, count in self.env['account.move']._read_group(
    #             domain=[('journal_id', 'in', sale_purchase_journals.ids), ('to_check', '=', True)],
    #             groupby=['journal_id'],
    #             aggregates=['amount_total_signed:sum', '__count'],
    #         )
    #     }
    #     fcurrency_id = self.company_id.fcurrency_id
    #     sale_purchase_journals._fill_dashboard_data_count(dashboard_data, 'account.move', 'entries_count', [])
    #     for journal in sale_purchase_journals:
    #         # User may have read access on the journal but not on the company
    #         currency = journal.currency_id or self.env['res.currency'].browse(journal.company_id.sudo().currency_id.id)
    #         (number_waiting, sum_waiting) = self._count_results_and_sum_amounts(query_results_to_pay[journal.id], currency)
    #         (number_draft, sum_draft) = self._count_results_and_sum_amounts(query_results_drafts[journal.id], currency)
    #         (number_late, sum_late) = self._count_results_and_sum_amounts(late_query_results[journal.id], currency)
    #         amount_total_signed_sum, count = to_check_vals.get(journal.id, (0, 0))
    #         dashboard_data[journal.id].update({
    #             'number_to_check': count,
    #             'to_check_balance': currency.format(amount_total_signed_sum),
    #             'title': _('Bills to pay') if journal.type == 'purchase' else _('Invoices owed to you'),
    #             'number_draft': number_draft,
    #             'number_waiting': number_waiting,
    #             'number_late': number_late,
    #             'sum_draft': currency.format(sum_draft),
    #             'sum_draft_fcurrency': formatLang(self.env, fcurrency_id.round(sum_draft) + 0.0, currency_obj=fcurrency_id),
    #             'sum_waiting': currency.format(sum_waiting),
    #             'sum_waiting_fcurrency': formatLang(self.env, fcurrency_id.round(sum_waiting) + 0.0, currency_obj=fcurrency_id),
    #             'sum_late': currency.format(sum_late),
    #             'sum_late_fcurrency': formatLang(self.env, fcurrency_id.round(sum_late) + 0.0, currency_obj=fcurrency_id),
    #             'has_sequence_holes': journal.has_sequence_holes,
    #             'is_sample_data': dashboard_data[journal.id]['entries_count'],
    #         })
    #     pass


    # def xxx_fill_sale_purchase_dashboard_data(self, dashboard_data):
    #     """Populate all sale and purchase journal's data dict with relevant information for the kanban card."""
    #     sale_purchase_journals = self.filtered(lambda journal: journal.type in ('sale', 'purchase'))
    #     if not sale_purchase_journals:
    #         return
    #     field_list = [
    #         "account_move.journal_id",
    #         "(CASE WHEN account_move.move_type IN ('out_refund', 'in_refund') THEN -1 ELSE 1 END) * account_move.amount_total_fcurrency AS amount_total",
    #         "account_move.amount_total_fcurrency AS amount_total_company",
    #         "account_move.fcurrency_id AS currency",
    #         "account_move.move_type",
    #         "account_move.invoice_date",
    #         "account_move.company_id",
    #     ]
    #     fcurrency_id = self.company_id.fcurrency_id
    #     query, params = sale_purchase_journals._get_open_bills_to_pay_query().select(*field_list)
    #     self.env.cr.execute(query, params)
    #     query_results_to_pay = group_by_journal(self.env.cr.dictfetchall())

    #     query, params = sale_purchase_journals._get_draft_bills_query().select(*field_list)
    #     self.env.cr.execute(query, params)
    #     query_results_drafts = group_by_journal(self.env.cr.dictfetchall())

    #     query, params = sale_purchase_journals._get_late_bills_query().select(*field_list)
    #     self.env.cr.execute(query, params)
    #     late_query_results = group_by_journal(self.env.cr.dictfetchall())

    #     to_check_vals = {
    #         vals['journal_id']: vals
    #         for vals in self.env['account.move'].read_group(
    #             domain=[('journal_id', 'in', sale_purchase_journals.ids), ('to_check', '=', True)],
    #             fields=['amount_total_fcurrency'],
    #             groupby='journal_id',
    #         )
    #     }

    #     curr_cache = {}
    #     sale_purchase_journals._fill_dashboard_data_count(dashboard_data, 'account.move', 'entries_count', [])
    #     for journal in sale_purchase_journals:
    #         currency = journal.currency_id or journal.company_id.currency_id
    #         (number_waiting, sum_waiting) = self._count_results_and_sum_amounts(query_results_to_pay[journal.id], currency, curr_cache=curr_cache)
    #         (number_draft, sum_draft) = self._count_results_and_sum_amounts(query_results_drafts[journal.id], currency, curr_cache=curr_cache)
    #         (number_late, sum_late) = self._count_results_and_sum_amounts(late_query_results[journal.id], currency, curr_cache=curr_cache)
    #         to_check = to_check_vals.get(journal.id, {})
    #         dashboard_data[journal.id].update({
    #             'number_to_check': to_check.get('__count', 0),
    #             'to_check_balance': to_check.get('amount_total_signed', 0),
    #             'title': _('Bills to pay') if journal.type == 'purchase' else _('Invoices owed to you'),
    #             'number_draft': number_draft,
    #             'number_waiting': number_waiting,
    #             'number_late': number_late,
    #             'sum_draft': currency.format(sum_draft * fcurrency_id.inverse_rate),
    #             'sum_draft_fcurrency': formatLang(self.env, fcurrency_id.round(sum_draft) + 0.0, currency_obj=fcurrency_id),
    #             'sum_waiting': currency.format(sum_waiting * fcurrency_id.inverse_rate),
    #             'sum_waiting_fcurrency': formatLang(self.env, fcurrency_id.round(sum_waiting) + 0.0, currency_obj=fcurrency_id),

    #             'sum_late': currency.format(sum_late * fcurrency_id.inverse_rate),
    #             'sum_late_fcurrency': formatLang(self.env, fcurrency_id.round(sum_late) + 0.0, currency_obj=fcurrency_id),

    #             'has_sequence_holes': journal.has_sequence_holes,
    #             'is_sample_data': dashboard_data[journal.id]['entries_count'],
    #         })