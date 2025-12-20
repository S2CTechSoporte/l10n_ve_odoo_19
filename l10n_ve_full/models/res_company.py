# -*- coding: UTF-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import re


class ResCompany(models.Model):
    _inherit = 'res.company'

    country_id = fields.Many2one('res.country', required=True, default=lambda self: self.env.ref('base.ve') )

    rif = fields.Char(string='RIF', related="vat", store=True)
    fax = fields.Char(string="Fax", size=13)
    allow_vat_wh_outdated = fields.Boolean(
        string="Permitir retención de IVA",
        help="Permite confirmar comprobantes de retención para anteriores o futuras "
             " fechas.")
    propagate_invoice_date_to_vat_withholding = fields.Boolean(
        string='Propagar fecha de factura a retención de IVA', default=False,
        help='Propague la fecha de la factura a la retención de IVA. Por defecto está en '
             'Falso.')

    #ISLR
    automatic_income_wh = fields.Boolean(
        'Retención Automática de Ingresos', default=False,
        help='Cuando sea cierto, la retención de ingresos del proveedor se'
             'validara automáticamente')
    propagate_invoice_date_to_income_withholding = fields.Boolean(
        'Propague la fecha de la factura a la retención de ingresos', default=False,
        help='Propague la fecha de la factura a la retención de ingresos. Por defecto es'
             'en falso')

    #ITF
    calculate_wh_itf = fields.Boolean(
        'Retención automática de ITF',
        help='Cuando sea Verdadero, la Retención de la ITF se validará automáticamente', default=False)
    wh_porcentage = fields.Float('Porcentaje ITF', help="El porcentaje a aplicar para retener", default=2)

    account_wh_itf_id = fields.Many2one('account.account', string="Cuenta ITF",
                                        help="Esta cuenta se utilizará en lugar de la predeterminada"
                                             "para generar el asiento del ITF")


    # IGTF Divisa
    aplicar_igtf_divisa = fields.Boolean(
        'Retención de IGTF Divisa',
        help='Cuando sea Verdadero, la Retención de la IGTF Cliente estará disponible en el pago de factura',
        default=False)
    igtf_divisa_porcentage = fields.Float('% IGTF Divisa', help="El porcentaje a aplicar para retener ")

    account_debit_wh_igtf_id = fields.Many2one('account.account', string="Cuenta Recibos IGTF",
                                               help="Esta cuenta se utilizará en lugar de la predeterminada"
                                                    "para generar el asiento del IGTF Divisa")

    account_credit_wh_igtf_id = fields.Many2one('account.account', string="Cuenta Pagos IGTF",
                                                help="Esta cuenta se utilizará en lugar de la predeterminada"
                                                     "para generar el asiento del IGTF Divisa")

    representante_legal = fields.Char(string='Representante Legal')
    representante_cedula = fields.Char(string='Cédula Representante Legal')
    firma_representante = fields.Binary(string='Firma Representante Legal')

    currency_l10n_id = fields.Many2one("res.currency",
                            string="Moneda de la Localización",
                            help="Moneda de Libros Compras y Ventas, Retenciones, etc",
                            domain=[('active', '=', True)],
                            default=lambda self: self.env.ref('base.VES') )

    def _default_currency_id(self):
        return self.env.ref('base.VES') #self.env.user.company_id.currency_id
    
    @api.constrains('vat')
    def _check_vat(self):
        for company in self:
            if company.country_id.code == 'VE':
                company.validate_vat_er(company.vat)
                company.validate_vat_duplicate(company.vat)
                   
    @api.constrains('email')
    def _check_mail(self):
        for company in self:
            if company.email:
                if not company.validate_email_addrs(self.email, 'email'):
                    raise UserError('El email es incorrecto. Ej: cuenta@dominio.xxx. Por favor intente de nuevo')

    @staticmethod
    def validate_vat_er(field_value):
        if field_value:
            patron = r'^[VEJGC]-\d{7,8}-\d$'
            # Validar la cadena
            if re.match(patron, field_value):
                return True
            else:
                raise UserError('El rif tiene el formato incorrecto. Ej: V-01234567-8, E-01234567-8, J-01234567-8 o G-01234567-8. Por favor verifique el formato y si posee los 12 caracteres como se indica en el Ej. e intente de nuevo')


    def validate_vat_duplicate(self, valor):
        if valor:
            partner_dup = self.search([('vat', '=', valor), ('id', '!=', self.id)],limit=1)
            if partner_dup.vat:
                raise UserError('El cliente o proveedor ya se encuentra registrado con el Documento: %s'
                    % (self.vat))
            else:
                return False

    @staticmethod
    def validate_email_addrs(email, field):
        res = {}
        mail_obj = re.compile(r"""
                    \b             # comienzo de delimitador de palabra
                    [\w.%+-]       # usuario: Cualquier caracter alfanumerico mas los signos (.%+-)
                    +@             # seguido de @
                    [\w.-]         # dominio: Cualquier caracter alfanumerico mas los signos (.-)
                    +\.            # seguido de .
                    [a-zA-Z]{2,3}  # dominio de alto nivel: 2 a 6 letras en minúsculas o mayúsculas.
                    \b             # fin de delimitador de palabra
                    """, re.X)  # bandera de compilacion X: habilita la modo verborrágico, el cual permite organizar
        # el patrón de búsqueda de una forma que sea más sencilla de entender y leer.
        if mail_obj.search(email):
            res = {
                field: email
            }
        return res