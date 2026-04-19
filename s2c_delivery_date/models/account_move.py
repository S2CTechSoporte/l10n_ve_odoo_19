from odoo import api, fields, models
from odoo.tools import frozendict


class AccountMove(models.Model):
    _inherit = 'account.move'

    delivery_time = fields.Integer(string="Tiempo de entrega", store=True, compute="_compute_delivery_time")

    @api.depends('delivery_date', 'invoice_date')
    def _compute_delivery_time(self):
        for record in self:
            record.delivery_time = 0
            if (record.delivery_date and record.invoice_date) and record.delivery_date > record.invoice_date:
                record.delivery_time = (record.delivery_date - record.invoice_date).days

    @api.depends('delivery_date', 'invoice_payment_term_id', 'invoice_date', 'currency_id', 'amount_total_in_currency_signed', 'invoice_date_due')
    def _compute_needed_terms(self):
        AccountTax = self.env['account.tax']
        for invoice in self.with_context(bin_size=False):
            is_draft = invoice.id != invoice._origin.id
            invoice.needed_terms = {}
            invoice.needed_terms_dirty = True
            sign = 1 if invoice.is_inbound(include_receipts=True) else -1
            if invoice.is_invoice(True) and invoice.invoice_line_ids:
                if invoice.invoice_payment_term_id:
                    if is_draft:
                        tax_amount_currency = 0.0
                        tax_amount = tax_amount_currency
                        untaxed_amount_currency = 0.0
                        untaxed_amount = untaxed_amount_currency
                        sign = invoice.direction_sign
                        base_lines, _tax_lines = invoice._get_rounded_base_and_tax_lines(round_from_tax_lines=False)
                        AccountTax._add_accounting_data_in_base_lines_tax_details(
                            base_lines,
                            invoice.company_id,
                            include_caba_tags=invoice.always_tax_exigible,
                        )
                        tax_results = AccountTax._prepare_tax_lines(base_lines, invoice.company_id)
                        for _base_line, to_update in tax_results['base_lines_to_update']:
                            untaxed_amount_currency += sign * to_update['amount_currency']
                            untaxed_amount += sign * to_update['balance']
                        for tax_line_vals in tax_results['tax_lines_to_add']:
                            tax_amount_currency += sign * tax_line_vals['amount_currency']
                            tax_amount += sign * tax_line_vals['balance']
                    else:
                        tax_amount_currency = invoice.amount_tax * sign
                        tax_amount = invoice.amount_tax_signed
                        untaxed_amount_currency = invoice.amount_untaxed * sign
                        untaxed_amount = invoice.amount_untaxed_signed
                    invoice_payment_terms = invoice.invoice_payment_term_id._compute_terms(
                        date_ref=invoice.delivery_date or invoice.invoice_date or invoice.date or fields.Date.context_today(invoice),
                        currency=invoice.currency_id,
                        tax_amount_currency=tax_amount_currency,
                        tax_amount=tax_amount,
                        untaxed_amount_currency=untaxed_amount_currency,
                        untaxed_amount=untaxed_amount,
                        company=invoice.company_id,
                        cash_rounding=invoice.invoice_cash_rounding_id,
                        sign=sign
                    )
                    for term_line in invoice_payment_terms['line_ids']:
                        key = frozendict({
                            'move_id': invoice.id,
                            'date_maturity': fields.Date.to_date(term_line.get('date')),
                            'discount_date': invoice_payment_terms.get('discount_date'),
                        })
                        values = {
                            'balance': term_line['company_amount'],
                            'amount_currency': term_line['foreign_amount'],
                            'discount_date': invoice_payment_terms.get('discount_date'),
                            'discount_balance': invoice_payment_terms.get('discount_balance') or 0.0,
                            'discount_amount_currency': invoice_payment_terms.get('discount_amount_currency') or 0.0,
                        }
                        if key not in invoice.needed_terms:
                            invoice.needed_terms[key] = values
                        else:
                            invoice.needed_terms[key]['balance'] += values['balance']
                            invoice.needed_terms[key]['amount_currency'] += values['amount_currency']
                else:
                    invoice.needed_terms[frozendict({
                        'move_id': invoice.id,
                        'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
                        'discount_date': False,
                        'discount_balance': 0.0,
                        'discount_amount_currency': 0.0
                    })] = {
                        'balance': invoice.amount_total_signed,
                        'amount_currency': invoice.amount_total_in_currency_signed,
                    }
