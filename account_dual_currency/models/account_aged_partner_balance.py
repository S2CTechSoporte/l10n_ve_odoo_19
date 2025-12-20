# -*- coding: utf-8 -*-
# vencida por cobrar y pagar
from odoo import models, fields

from dateutil.relativedelta import relativedelta
from itertools import chain

class AgedPartnerBalanceCustomHandler(models.AbstractModel):
    _inherit = 'account.aged.partner.balance.report.handler'

    fcurrency_id = fields.Many2one("res.currency",
                            string="Moneda ¤",
                            default=lambda self: self.env.company.fcurrency_id )
    
    fcurrency = fields.Char(string="Moneda ¤" )     
    
    total_fcurrency = fields.Monetary("Total ¤", currency_field='fcurrency_id' )

    def _prepare_partner_values(self):
        columns = super()._prepare_partner_values()
        if columns:
            columns.update( {
                'fcurrency': None,
                'total_fcurrency': None
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
        cxp = self.env.ref('account_reports.aged_payable_report').id
		
        if options['report_id'] not in (cxc, cxp):
            return rslt

        self.fcurrency_id = self.env.company.fcurrency_id
        if isinstance(rslt, dict): 
            residual = self._get_fcurrency_data(options)
            rslt.update(
                {
                    'fcurrency':  self.env.company.fcurrency_id.name,
                    'total_fcurrency': residual
                }
            )

        if isinstance(rslt, list):
            for id, value in  rslt:
                partner_id = None
                line_id = None
                if current_groupby == 'partner_id':
                    partner_id = id
                
                if current_groupby == 'id':
                    line_id = id

                residual = self._get_fcurrency_data(options, partner_id=partner_id, line_id=line_id)
                value.update(
                    {
                        'fcurrency': self.env.company.fcurrency_id.name,
                        'total_fcurrency': residual
                    }  
                )

        return rslt
	
    def _get_fcurrency_data(self, options, partner_id=None, line_id=None):
        report_id = options['report_id']
        account_type = None
        period = None
        trade_type = None
        partner_ids = None
        partner_categories = None
        
        if report_id == self.env.ref('account_reports.aged_receivable_report').id:
			# por cobrar
            account_type = [('account_id.account_type', '=', 'asset_receivable')]
        
        if report_id == self.env.ref('account_reports.aged_payable_report').id:
			# por pagar
            account_type = [('account_id.account_type', '=', 'liability_payable')]
        
        date_from = None
        date_to = None
        period_type = options['date']['period_type']
		
        if period_type in ('today', 'custom'):
            date_to = perido_type = options['date']['date_to']
            period = [('date', '<=', date_to)]
        else:
            date_from = options['date']['date_from']
            date_to = options['date']['date_to']
            period = [('date','>=', date_from),('date', '<=', date_to)]
		
        for trade in options['account_type']:
            value_trade = []
            if trade['id'] == 'trade_receivable' and trade['selected'] == True:
                value_trade.append(False)
        
            if  trade['id'] == 'non_trade_receivable' and trade['selected'] == True:
                value_trade.append(True)
            
            if  value_trade:
                trade_type = [('account_id.non_trade', 'in', value_trade)] 
        
        if options['partner_ids']:
            partner_ids =  [('partner_id', 'in', tuple(options['partner_ids']))]
        
        if options['partner_categories']:
            partner_categories =  [('partner_id.category_id', 'in', tuple(options['partner_categories']))]
        
        domain = [('parent_state', '=', 'posted')]
        
        if account_type:
            domain += account_type
        
        if period:
            domain += period
        
        if trade_type:
            domain += trade_type
        
        if partner_ids:
            domain += partner_ids
        
        if partner_categories:
            domain += partner_categories
        
        if partner_id:
            domain += [('partner_id','=', partner_id)]
        
        if line_id:
            domain += [('id','=', line_id)]
            move_line = self.env['account.move.line'].browse(line_id).exists()
        else:
            move_line = self.env['account.move.line'].search(domain)
        residual = sum(move_line.mapped('amount_residual_fcurrency'))
        return round(residual, 2)