# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    fcurrency_id = fields.Many2one("res.currency", related="move_id.fcurrency_id", store=True)
    tax_today = fields.Float(related="move_id.tax_today", store=True, digits='Dual_Currency_rate')
    edit_trm =  fields.Boolean(related="move_id.edit_trm")

    # conversion_rate = fields.Monetary(
    #     compute='_compute_conversion_rate',
    #     help="Currency rate from company currency to document currency.",
    #     store=True,
    #     currency_field='company_currency_id',
    #     copy=False
    # )

    debit_fcurrency = fields.Float(
        string='Débito ¤', 
        store=True, 
        compute="_compute_debit_credit", 
        readonly=False, digits=(12,4))

    credit_fcurrency = fields.Float(
        string='Crédito ¤', store=True,
        compute="_compute_debit_credit", 
        readonly=False, 
        digits=(12,4))
    
    price_unit_fcurrency = fields.Monetary(
        currency_field='fcurrency_id', 
        string='Precio ¤', 
        store=True,
        compute='_compute_price_unit',
        readonly=False)
    
    price_subtotal_fcurrency = fields.Monetary(
        currency_field='fcurrency_id', 
        string='SubTotal ¤', 
        store=True,
        compute="_compute_totals")
    
    amount_residual_fcurrency = fields.Monetary(
        string='Residual Amount ¤', 
        #compute='_compute_amount_residual', 
        store=True, currency_field='fcurrency_id',readonly=False,
        help="The residual amount on a journal item expressed in the company currency.")
    
    balance_fcurrency = fields.Monetary(
        string='Balance ¤',
        currency_field='fcurrency_id', 
        store=True, readonly=False,
        compute='_compute_balance',
        help="Technical field holding the debit_fcurrency - credit_fcurrency in order to open meaningful graph views from reports")

    date_maturity_fcurrency = fields.Date(
        string='Due Date',
        index=True,
        compute='_compute_date_maturity_fcurrency',
        store=True,
        help="se usará para el vencimiento de la factura en la moneda secundaria",
    )

    @api.depends('date', 'date_maturity')
    def _compute_date_maturity_fcurrency(self):
        for line in self:
            if line.date_maturity:
                line.date_maturity_fcurrency = line.date_maturity
            else:
                line.date_maturity_fcurrency = line.date

    def _get_dual_currency_rate_date(self):
        """Return the date to use for currency conversions.

        Odoo 19 removed `account.move.line._get_rate_date()`. The core logic
        generally relies on the move's accounting date.
        """
        self.ensure_one()
        return self.move_id.date or self.move_id.invoice_date or fields.Date.context_today(self)

    def _compute_balance(self):
        res = super(AccountMoveLine, self)._compute_balance()
        for line in self:
            # el balance siempre se da en la moneda de la empresa
            if line.balance:
                currency = line.company_id.fcurrency_id
                company = line.company_id
                date = line._get_dual_currency_rate_date()
                line.balance_fcurrency = company.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert(line.balance, currency, company, date, False)
                line.amount_residual_fcurrency = line.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert(line.amount_residual_currency, currency, company, date, False)
        return res
    
    @api.onchange('amount_currency', 'currency_id')
    def _inverse_amount_currency(self):
        res = super()._inverse_amount_currency()
        for line in self:
            # el balance siempre se da en la moneda de la empresa
            if line.balance:
                currency = line.company_id.fcurrency_id
                company = line.company_id
                date = line._get_dual_currency_rate_date()
                line.balance_fcurrency = company.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert(line.balance, currency, company, date, False)
                line.amount_residual_fcurrency = line.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert(line.amount_residual_currency, currency, company, date, False)
        return res

    def _compute_totals(self):
        res = super(AccountMoveLine, self)._compute_totals()
        for line in self:
            currency = line.company_id.fcurrency_id
            company = line.company_id
            date = line._get_dual_currency_rate_date()
            line.price_subtotal_fcurrency = line.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert(line.price_subtotal, currency, company, date, False)
            if line.price_unit:
                line.price_unit_fcurrency = line.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert(line.price_unit, currency, company, date, False)

        return res

    def _compute_price_unit(self):
        res = super(AccountMoveLine, self)._compute_price_unit()
        for line in self:
            if line.price_unit:
                currency = line.company_id.fcurrency_id
                company = line.company_id
                date = line._get_dual_currency_rate_date()
                line.price_unit_fcurrency = line.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert(line.price_unit, currency, company, date, False)
        return res

    def _compute_debit_credit(self):
        res = super(AccountMoveLine, self)._compute_debit_credit()
        for line in self:
            
            fcurrency = line.company_id.fcurrency_id
            company =  line.company_id

            date = line._get_dual_currency_rate_date()
                
            if line.debit != 0:
                line.debit_fcurrency = line.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert( abs( line.amount_currency), fcurrency, company, date,False)

            if line.credit != 0:
                line.credit_fcurrency = line.currency_id.with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._convert( abs( line.amount_currency), fcurrency, company, date,False)


        return res
    
    def _compute_currency_rate(self):
        # Tasa que se usa en los campos estandar debit y credit
        # cuando no se usa la moneda de la empresa
        for line in self:
            if line.currency_id:
                date = line._get_dual_currency_rate_date()

                line.currency_rate = self.env['res.currency'].with_context({'edit_trm': line.edit_trm, 'tax_today': line.tax_today})._get_conversion_rate(
                    from_currency=line.company_currency_id,
                    to_currency=line.currency_id,
                    company=line.company_id,
                    date=date,
                )
            else:
                line.currency_rate = 1
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        if 'tax_today' not in fields:
            return super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                           orderby=orderby, lazy=lazy)
        res = super(AccountMoveLine, self).read_group(domain, fields, groupby, offset=offset, limit=limit,
                                                      orderby=orderby, lazy=lazy)
        for group in res:
            if group.get('__domain'):
                records = self.search(group['__domain'])
                group['tax_today'] = 0
        return res



