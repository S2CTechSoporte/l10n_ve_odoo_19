# -*- coding: utf-8 -*-
# vencida por cobrar
from odoo import models, fields

from dateutil.relativedelta import relativedelta
from itertools import chain

from datetime import date
from datetime import datetime


class AgedPartnerBalanceCustomHandler(models.AbstractModel):
    _inherit = 'account.aged.partner.balance.report.handler'

    # def _report_custom_engine_aged_receivable(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
    #     result = super()._report_custom_engine_aged_receivable(expressions, options, date_scope, current_groupby, next_groupby, offset, limit, warnings)
    #     return result

    def _custom_line_postprocessor(self, report, options, lines, warnings=None):
        lines = super()._custom_line_postprocessor(report, options, lines, warnings)
        
        report = self.env['account.report'].browse(options['report_id'])
        for line in lines:
            move_line = report._get_res_id_from_line_id(line['id'], 'account.move.line')
            if move_line:
                move_line = self.env['account.move.line'].browse(move_line)
                
                for column in line['columns']:
                    if column.get('expression_label') == 'delivery_date':
                        column.update(
                            {
                                'name': move_line.move_id.delivery_date.strftime('%d-%m-%Y') if move_line.move_id.delivery_date else '',
                                'no_format': move_line.move_id.delivery_date
                            }
                        )

                    if column.get('expression_label') == 'delivery_time':
                        column.update(
                            {
                                'name': f'{move_line.move_id.delivery_time}\xa0días' if move_line.move_id.delivery_time else '',
                                'no_format': move_line.move_id.delivery_date
                            }
                        )
                    
                    if column.get('expression_label') == 'invoice_date_due':
                        column.update(
                            {
                                'name': move_line.move_id.invoice_date_due.strftime('%d-%m-%Y') if move_line.move_id.invoice_date_due else '',
                                'no_format': move_line.move_id.invoice_date_due
                            }
                        )
                    
                    if column.get('expression_label') == 'remaining_days':
                        ramaining_days = self._compute_remaining_days(move_line.move_id.invoice_date_due)
                        column.update(
                            {
                                'name': ramaining_days,
                                'no_format': ramaining_days
                            }
                        )

        return lines

    def _prepare_partner_values(self):
        columns = super()._prepare_partner_values()
        if columns:
            columns.update( {
                'delivery_date': None,
                'delivery_time': None,
                'invoice_date_due': None,
                'remaining_days': None
            })
        return columns    
    
    def _prepare_partner_values(self):
        columns = super()._prepare_partner_values()
        if columns:
            columns.update( {
                'delivery_date': None,
                'delivery_time': None,
                'invoice_date_due': None,
                'remaining_days': None
            })
        return columns
    
    def _aged_partner_report_custom_engine_common(self, options, internal_type, current_groupby, 
		next_groupby, offset=0, limit=None):
        rslt =  super()._aged_partner_report_custom_engine_common(options, 
			internal_type, 
			current_groupby, 
			next_groupby,
			offset,
			limit)

        cxc = self.env.ref('account_reports.aged_receivable_report').id
		
        if options['report_id'] != cxc:
            return rslt
        
        if isinstance(rslt, dict):
            rslt.update({
                'delivery_date': None,
                'delivery_time': None,
                'invoice_date_due': None,
                'remaining_days': None
            })
        
        if isinstance(rslt, list):
            for id, value in  rslt:
                value.update(
                        {
                            'delivery_date':  None,
                            'delivery_time': None,
                            'invoice_date_due': None,
                            'remaining_days': None
                        }
                    )


        return rslt
    
    def _compute_remaining_days(self, invoice_date_due):
        if invoice_date_due:
            remaining_days = (invoice_date_due - date.today()).days
            if remaining_days == 0:
                return 'Hoy'
            elif remaining_days == 1:
                return 'Mañana'
            elif remaining_days == -1:
                return 'Ayer'

            if remaining_days < -1:
                return f'Hace %s días' % abs(remaining_days)
            else:
                if remaining_days > 1 and remaining_days <= 120:
                    return f'En %s días' % remaining_days
                else:
                    return 'En más de 120 días'           

        return None
	
    