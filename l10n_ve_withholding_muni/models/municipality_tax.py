# -*- coding: utf-8 -*-

import logging
from datetime import datetime, date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger("__name__")


class PeriodMonth(models.Model):
    _name = 'period.month'
    _description = 'period.month'
    _rec_name = 'months_number'

    name = fields.Char(string='Months')
    months_number = fields.Char(string='Number')


class PeriodYear(models.Model):
    _name = 'period.year'
    _description = 'period.year'

    name = fields.Char(string='year')


class MuniWhConcept(models.Model):
    _name = 'muni.wh.concept'
    _description = 'muni.wh.concept'

    name = fields.Char(string="Description", required=True)
    code = fields.Char(string='Activity code', required=True)
    aliquot = fields.Float(string='Aliquot', required=True)
    month_ucim = fields.Char(string='UCIM per month')
    year_ucim = fields.Char(string='UCIM per year')



class MunicipalityTaxLine(models.Model):
    _name = 'municipality.tax.line'
    _description = 'municipality.tax.line'

    wh_concept_id = fields.Many2one('muni.wh.concept', string="Retention concept", copy=False)
    code = fields.Char(string='Activity code', store=True)
    aliquot = fields.Float(string='Aliquot')
    base_tax = fields.Float(string='Base Tax')
    wh_amount = fields.Float(compute="_compute_wh_amount", string='Withholding Amount', store=True)
    type = fields.Selection(selection=[('purchase', 'Purchase'), ('service', 'Service'), ('dont_apply','Does not apply')],string='Type of transaction')
    l10n_ve_withholding_muni_id = fields.Many2one('municipality.tax', string='Municipality')
    move_id = fields.Many2one('account.move', string='Account entry')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    invoice_date = fields.Date(string="Invoice Date")
    invoice_number = fields.Char(string="Invoice Number")
    invoice_ctrl_number = fields.Char(string="Invoice Control Number")
    boleano_tal = fields.Boolean('valor', default=False)

    def float_format(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result


    """@api.depends('base_tax', 'aliquot')
    def _compute_wh_amount(self):
        # for line in self.act_code_ids:
        # if self.base_tax and self.aliquot:
        _logger.info("\n\n\n\n Se esta realizando el calculo \n\n\n\n")
        retention = ((self.base_tax * self.aliquot) / 100)
        _logger.info("\n\n\n retention %s\n\n\n", retention)
        self.wh_amount = retention
        muni_tax = self.env['municipality.tax'].browse(self.l10n_ve_withholding_muni_id.id)
        withheld_amount = self.base_tax
        amount = retention
        if muni_tax:
            muni_tax.write({'withheld_amount': withheld_amount, 'amount': retention})"""

    @api.depends('base_tax', 'aliquot')
    def _compute_wh_amount(self):
        # for line in self.act_code_ids:
        # if self.base_tax and self.aliquot:
        withheld_amount=0
        cont = 0
        amount=0
        for item in self:
            cont = cont + 1
            if self[0].boleano_tal == True:
                return
            else:

                retention = ((item.base_tax * item.aliquot) / 100)
                item.wh_amount = retention
                muni_tax = self.env['municipality.tax'].browse(item.l10n_ve_withholding_muni_id.id)
                # withheld_amount = item.base_tax
                # amount = amount+retention

                withheld_amount = withheld_amount + item.base_tax  # correccion darrell se transformo en acumulador
                amount = amount + item.wh_amount
                # correccion darrell se transformo en acumulador
                # if self[0].l10n_ve_withholding_muni_id:
        self[0].l10n_ve_withholding_muni_id.write({'withheld_amount': withheld_amount, 'amount': amount})
        self[0].boleano_tal = True
            # muni_tax.write({'withheld_amount': withheld_amount, 'amount': retention})


class MUnicipalityTax(models.Model):
    _name = 'municipality.tax'
    _description = 'municipality.tax'

    def doc_cedula(self,aux):
        #nro_doc=self.partner_id.vat
        document = ''
        busca_partner = self.env['res.partner'].search([('id','=',aux)])
        for det in busca_partner:

            if det.company_type == 'person':
                if det.vat:
                    document = det.vat
                else:
                    if det.nationality == 'V' or det.nationality == 'E':
                        document = str(det.nationality) + str(det.identification_id)
                    else:
                        document = str(det.identification_id)
            else:
                if det.vat:
                    document = det.vat
                else:
                    document = 'N/A'
        return document

    def float_format2(self,valor):
        #valor=self.base_tax
        if valor:
            result = '{:,.2f}'.format(valor)
            result = result.replace(',','*')
            result = result.replace('.',',')
            result = result.replace('*','.')
        else:
            result="0,00"
        return result


    @api.model
    def _type(self):
        """Return invoice type."""
        origin = self._context.get('type') 
        if self._context.get('type'):
            return self._context.get('type')

    wh_muni_id = fields.Many2one('account.move', string='Asiento Contable', readonly=True, copy=False)
    name = fields.Char(string='Voucher number', default='New')
    state = fields.Selection(selection=[
            ('draft', 'Draft'),
            ('posted', 'Posted'),
            ('cancel', 'Cancelled')
        ], string='Status', readonly=True, copy=False,
        default='draft')
    transaction_date = fields.Date(string='Transacción Date', default=datetime.now())
    #period fields
    date_start = fields.Many2one('period.month', string='Date start')
    date_end = fields.Many2one('period.year', string='Date end')
    rif = fields.Char(string='RIF')
    #rif = fields.Char(related='invoice_id.rif',string='RIF')
    # address
    address = fields.Char(compute="_get_address", string='Address')
    # partner data
    partner_id = fields.Many2one('res.partner', string='Partner')
    act_code_ids = fields.One2many('municipality.tax.line', 'l10n_ve_withholding_muni_id', string='Activities code')
    # campos de ubicacion politico territorial
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    municipality_id = fields.Many2one('res.country.state.municipality', string='Municipality')
    invoice_id = fields.Many2one('account.move', string='Invoice')
    amount = fields.Float(string='Amount')
    withheld_amount = fields.Float(string='Withheld Amount')
    type = fields.Selection(selection=[
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice','Supplier Invoince'),
        ('in_refund','Suplier Refund'),
        ('out_refund','Customer Refund'),
        ('in_receipt','Nota Debito cliente'),
        ('out_receipt','Nota Debito proveedor'),
        ], string="Type invoice", store=True, default=_type)
    
    # We need this field for the reports
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    move_id = fields.Many2one('account.move', string='Id del movimiento')
    invoice_number=fields.Char(string='Nro de Factura')

    #@api.depends('invoice_id')
    def _factura_prov_cli(self):
        self.invoice_number="...."
        #factura= self.env['account.move'].search([('name','=',self.invoice_id.id)])
        #for det in factura:
            #invoice_number=det.invoice_number
        #self.invoice_number= str(invoice_number)

    @api.onchange('partner_id')
    def _rif(self):
        if self.partner_id:
            #self.rif = self.partner_id.vat
            self.rif = (self.partner_id.vat)


    @api.depends('partner_id')
    def _get_address(self):
        location = ''
        streets = ''
        if self.partner_id:
            location = self._get_state_and_city()
            streets = self._get_streets()
            self.address = streets + " " + location
        else:
            self.address = ''


    def _get_state_and_city(self):
        state = ''
        city = ''
        if self.partner_id.state_id:
            state = "Edo." + " " + str(self.partner_id.state_id.name or '')
        if self.partner_id.city:
            city = str(self.partner_id.city or '')
        result = city + " " + state
        return  result 


    def _get_streets(self):
        street2 = ''
        av = ''
        if self.partner_id.street:
            av = str(self.partner_id.street or '')
        if self.partner_id.street2:
            street2 = str(self.partner_id.street2 or '')
        result = av + " " + street2
        return result


    def get_company_address(self):
        location = ''
        streets = ''
        if self.company_id:
            streets = self._get_company_street()
            location = self._get_company_state_city()
        return  (streets + " " + location)


    def _get_company_street(self):
        street2 = ''
        av = ''
        if self.company_id.street:
            av = str(self.company_id.street or '')
        if self.company_id.street2:
            street2 = str(self.company_id.street2 or '')
        result = av + " " + street2
        return result


    def _get_company_state_city(self):
        state = ''
        city = ''
        if self.company_id.state_id:
            state = "Edo." + " " + str(self.company_id.state_id.name or '')
        if self.company_id.city:
            city = str(self.company_id.city or '')
        result = city + " " + state
        return  result



    def action_post(self):
       """Confirmed the municipal retention voucher."""
       if not self.transaction_date:
            raise ValidationError("Debe establecer una fecha de Transacción")
       self.state = 'posted'
       valor=self.registro_movimiento_linea_retencion(self.name)
       valor.action_post()
       self.wh_muni_id = valor

    def action_cancel(self):
        """ Call cancel_move and return True"""
        if self.state in ['posted', 'draft']:
            if self.wh_muni_id: self.wh_muni_id._reverse_moves([{'date': fields.Date.today(), 'ref': _('Reversión %s' % self.wh_muni_id.name)}], cancel=True)
            if self.invoice_id: self.invoice_id.write({'wh_muni_id': False})
            self.write({'state': 'cancel'})
        else:
            raise ValidationError(_("""La retencion debe estar en estado Publicado para poder ser cancelada"""))
        return True



    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':

            if vals['type']=="in_invoice" or vals['type']=="in_refund" or vals['type']=="in_receipt":
                    vals['name'] = self.get_name() #self.env['ir.sequence'].next_by_code('l10n_ve_cuenta_retencion_municipal') or '/'
                    invoice = self.env['account.move'].search([('id','=',vals['invoice_id'])])
                    if invoice.date.month not in [10,11,12]:
                        month = '0'+str(invoice.date.month)
                    else:
                        month = invoice.date.month
                    vals['name'] = str(invoice.date.year) + str(month) + str(vals['name'])

        return super().create(vals)


    def conv_div_extranjera(self,valor):
        self.invoice_id.currency_id.id
        fecha_contable_doc=self.invoice_id.date
        monto_factura=self.invoice_id.amount_total
        valor_aux=0
        #raise UserError(_('moneda compañia: %s')%self.company_id.currency_id.id)
        if self.invoice_id.currency_id.id != self.company_id.currency_id.id:
            dt = fields.datetime.combine(self.invoice_id.date, fields.datetime.max.time())
            tasa= self.env['res.currency.rate'].search(
                [('currency_id','=',
                self.invoice_id.currency_id.id),
                ('rate_date','<=', dt)], 
                order="rate_date asc")
            for det_tasa in tasa:
                if fecha_contable_doc>=det_tasa.name:
                    valor_aux=det_tasa.rate
            rate=round(1/valor_aux,2)  # LANTA
            #rate=round(valor_aux,2)  # ODOO SH
            resultado=valor/rate
        else:
            resultado=valor
        return resultado

    # def registro_movimiento_retencion(self,consecutivo_asiento):
    #     name = consecutivo_asiento
    #     signed_amount_total=0
    #     #raise UserError(_('self.move_id.name = %s')%self.invoice_id.name)
    #     if self.type=="in_invoice":
    #         signed_amount_total=self.amount #self.conv_div_extranjera(self.amount)
    #     if self.type=="out_invoice":
    #         signed_amount_total=-1*self.amount #(-1*self.conv_div_extranjera(self.amount))
    #
    #     if self.type=="out_invoice" or self.type=="out_refund" or self.type=="out_receipt":
    #         id_journal=self.partner_id.purchase_jrl_id.id
    #     if self.type=="in_invoice" or self.type=="in_refund" or self.type=="in_receipt":
    #         id_journal=self.company_id.partner_id.purchase_jrl_id.id
    #
    #     value = {
    #         'name': name,
    #         'date': self.transaction_date,#listo
    #         #'amount_total':self.vat_retentioned,# LISTO
    #         'partner_id': self.partner_id.id, #LISTO
    #         'journal_id':id_journal,
    #         'ref': "Retencion del Impuesto Municipal de la Factura %s" % (self.invoice_id.name),
    #         #'amount_total':self.vat_retentioned,# LISTO
    #         #'amount_total_signed':signed_amount_total,# LISTO
    #         'type': "entry",# estte campo es el que te deja cambiar y almacenar valores
    #         'wh_muni_id': self.id,
    #     }
    #     move_obj = self.env['account.move']
    #     move_id = move_obj.create(value)
    #     return move_id


    def registro_movimiento_linea_retencion(self,consecutivo_asiento):
        name = consecutivo_asiento
        valores = self.amount #self.conv_div_extranjera(self.amount) #VALIDAR CONDICION
        cero = 0.0
        cuenta_debe = 0
        cuenta_haber = 0
        l2 = []
        if self.type=="out_invoice" or self.type=="out_refund" or self.type=="out_receipt":
            cuenta_ret_cliente=self.company_id.account_ret_muni_receivable_id.id# cuenta retencion cliente
            cuenta_ret_proveedor=self.company_id.account_ret_muni_payable_id.id#cuenta retencion proveedores
            cuenta_clien_cobrar=self.partner_id.property_account_receivable_id.id
            cuenta_prove_pagar = self.partner_id.property_account_payable_id.id

        if self.type=="in_invoice" or self.type=="in_refund" or self.type=="in_receipt":
            cuenta_ret_cliente=self.company_id.account_ret_muni_receivable_id.id# cuenta retencion cliente
            cuenta_ret_proveedor=self.company_id.account_ret_muni_payable_id.id#cuenta retencion proveedores
            cuenta_clien_cobrar=self.partner_id.property_account_receivable_id.id
            cuenta_prove_pagar = self.partner_id.property_account_payable_id.id

        tipo_empresa=self.type
        #raise UserError(_('darrell = %s')%tipo_empresa)
        if tipo_empresa=="in_invoice" or tipo_empresa=="in_receipt":#aqui si la empresa es un proveedor
            cuenta_haber=cuenta_ret_proveedor
            cuenta_debe=cuenta_prove_pagar
            #raise UserError(_(' pantalla 1'))
            #raise UserError(_('cuentas = %s')%cuenta_debe)

        if tipo_empresa=="in_refund":
            cuenta_haber=cuenta_prove_pagar
            cuenta_debe=cuenta_ret_proveedor
            #raise UserError(_(' pantalla 2'))

        if tipo_empresa=="out_invoice" or tipo_empresa=="out_receipt":# aqui si la empresa es cliente
            cuenta_haber=cuenta_clien_cobrar
            cuenta_debe=cuenta_ret_cliente
            #raise UserError(_(' pantalla 3'))

        if tipo_empresa=="out_refund":
            cuenta_haber=cuenta_ret_cliente
            cuenta_debe=cuenta_clien_cobrar
            #raise UserError(_(' pantalla 4'))
        balances=cero-valores
        journal_lines = []

        journal_lines.append(
            (0, 0, {
                'account_id': cuenta_haber,
                'partner_id': self.partner_id.id,
                'name': name,
                'debit': 0.00,
                'credit': valores,
            }),
        )
        journal_lines.append(
            (0, 0, {
                'account_id': cuenta_debe,
                'partner_id': self.partner_id.id,
                'name': name,
                'debit': valores,
                'credit': 0.00,
            }),
        )

        journal_item = self.env['account.move'].create({
            'ref': "Retencion Impuesto Municipal de la Factura %s" % (self.invoice_id.name),
            'journal_id': self.company_id.purchase_jrl_id.id,
            'line_ids': journal_lines,
            'move_type': 'entry',
            'state': 'draft',
            'date': self.invoice_id.date,
            'invoice_date': self.invoice_id.invoice_date
        })

        return journal_item



    def get_name(self):
        '''metodo que crea el Nombre del asiento contable si la secuencia no esta creada, crea una con el
        nombre: 'l10n_ve_cuenta_retencion_iva'''

        #self.ensure_one()
        SEQUENCE_CODE = 'l10n_ve_cuenta_retencion_municipal'
        company_id = self.company_id or self.env.company
        IrSequence = self.env['ir.sequence'].with_company(company_id)
        name = IrSequence.next_by_code(SEQUENCE_CODE)

        # si aún no existe una secuencia para esta empresa, cree una
        if not name:
            IrSequence.sudo().create({
                'prefix': '',
                'name': 'Localización Venezolana Retenciones Municipales',
                'code': SEQUENCE_CODE,
                'implementation': 'no_gap',
                'padding': 5,
                'number_increment': 1,
                'company_id': company_id.id,
            })
            name = IrSequence.next_by_code(SEQUENCE_CODE)
        return name
