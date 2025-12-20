# -*- coding: UTF-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError
import re

class ResPartner(models.Model):
    _inherit = 'res.partner'
 
    nationality = fields.Selection([
        ('V', 'Venezolano'),
        ('E', 'Extranjero'),
        ('P', 'Pasaporte')], string="Tipo Documento", default='V')
    identification_id = fields.Char(string='Documento de Identidad')
    value_parent = fields.Boolean(string='Valor parent_id', compute='compute_value_parent_id')
    people_type_individual = fields.Selection([
        ('pnre', 'PNRE Persona Natural Residente'),
        ('pnnr', 'PNNR Persona Natural No Residente')
    ], string='Tipo de Persona individual', default='pnre')
    people_type_company = fields.Selection([
        ('pjdo', 'PJDO Persona Jurídica Domiciliada'),
        ('pjnd', 'PJND Persona Jurídica No Domiciliada')], string='Tipo de Persona compañía', default='pjdo')
    
    #vat = fields.Char(tracking=False)
    rif = fields.Char(string='RIF', 
        related="vat", store=True, tracking=False, 
        help="Este campo se mantiene por compatibilidad con versiones anteriores de la Localización")

    wh_iva_agent = fields.Boolean(
        '¿Es Agente de Retención (IVA)?',
        help="Indique si el socio es un agente de retención de IVA", default=True)

    wh_iva_rate = fields.Float(
        string='% Retención de IVA',
        help="Se coloca el porcentaje de la Tasa de retención de IVA", default=75.0)

    vat_subjected = fields.Boolean('Declaración legal de IVA',
    help="Marque esta casilla si el socio está sujeto al IVA. Se utilizará para la declaración legal del IVA.", default=True)

    purchase_journal_id = fields.Many2one('account.journal','Diario de Compra para IVA', company_dependent=True,
                                        domain="[('is_iva_journal','=', True), ('company_id', '=', current_company_id)]")
    purchase_sales_id = fields.Many2one('account.journal', 'Diario de Venta para IVA', company_dependent=True,
                                        domain="[('is_iva_journal','=', True), ('company_id', '=', current_company_id)]")

    ## ISLR #######################
    islr_withholding_agent = fields.Boolean(
        '¿Agente de retención de ingresos?', default=True,
        help="Verifique si el partner es un agente de retención de ingresos")
    spn = fields.Boolean(
        '¿Es una sociedad de personas físicas?',
        help='Indica si se refiere a una sociedad de personas físicas.')
    islr_exempt = fields.Boolean(
        '¿Está exento de retención de ingresos?',
        help='Si el individuo está exento de retención de ingresos')
    purchase_islr_journal_id = fields.Many2one('account.journal', 'Diario de Compra para ISLR', company_dependent=True,
                                        domain="[('is_islr_journal','=', True), ('company_id', '=', current_company_id)]")
    sale_islr_journal_id = fields.Many2one('account.journal', 'Diario de Venta para ISLR', company_dependent=True,
                                        domain="[('is_islr_journal','=', True), ('company_id', '=', current_company_id)]")

    same_vat_partner_id = fields.Many2one('res.partner', string='Contacto con el mismo RIF',
                                          compute='_compute_same_rif_partner_id', store=False)

    contribuyente_seniat = fields.Selection([
        ('ordinario', 'Ordinario'),
        ('especial', 'Especial'),
        ('formal', 'Formal'),
        ('gobernamental', 'Gubernamental')], string="Contribuyente", default='ordinario')
    
    country_id = fields.Many2one('res.country', default=lambda self: self.env.ref('base.ve') )

    @api.constrains('identification_id')
    def _check_identification_id(self):
        for partner in self:
            partner.validation_document_ident(partner.identification_id, partner.nationality)
            partner.validate_ci_duplicate(partner.identification_id)
            
    @api.constrains('rif')
    def _check_rif(self):
        for partner in self:
            if (partner.company_type == 'company' and partner.people_type_company == 'pjdo') or (partner.company_type == 'individual' and partner.people_type_individual == 'pnre'):    
                partner.validate_rif_er(partner.rif)
                partner.validate_rif_duplicate(partner.rif)
                   
    @api.constrains('email')
    def _check_mail(self):
        if self.email:
            if not self.validate_email_addrs(self.email, 'email'):
                raise UserError('El email es incorrecto. Ej: cuenta@dominio.xxx. Por favor intente de nuevo')

    @api.depends('rif', 'company_id')
    def _compute_same_rif_partner_id(self):
        for partner in self:
            # use _origin to deal with onchange()
            partner_id = partner._origin.id
            # active_test = False because if a partner has been deactivated you still want to raise the error,
            # so that you can reactivate it instead of creating a new one, which would loose its history.
            Partner = self.with_context(active_test=False).sudo()
            domain = [
                ('rif', '=', partner.rif),
                ('company_id', 'in', [False, partner.company_id.id]),
            ]
            if partner_id:
                domain += [('id', '!=', partner_id), '!', ('id', 'child_of', partner_id)]
            partner.same_vat_partner_id = bool(partner.rif) and not partner.parent_id and Partner.search(domain,
                                                                                                         limit=1)

    @api.constrains('vat', 'vat_type', 'country_id')
    def check_vat(self):
        for rec in self:
            if rec.country_id:
                if rec.country_id.code == 'VE':
                    return
                else:
                    return super().check_vat()

            
    @api.depends('company_type')
    def compute_value_parent_id(self):
        for rec in self:
            rec.value_parent = rec.parent_id.active

    @staticmethod
    def validation_document_ident(valor, nationality):
        if valor:
            if nationality == 'V' or nationality == 'E':
                if len(valor) < 7 or len(valor) > 8:
                    raise UserError('La Cedula de Identidad no puede ser menor que 7 cifras ni mayor a 8.')
                
                if not valor.isdigit():
                    raise UserError(
                        'La Cédula solo debe ser Numerico. Por favor corregir para proceder a Crear/Editar el registro')

            if nationality == 'P':
                if (len(valor) > 20) or (len(valor) < 10):
                    raise UserError('El Pasaporte no puede ser menor que 10 cifras ni mayor a 20.')

    def validate_ci_duplicate(self, valor):
        partner_dup = self.search([('identification_id', '=', valor), ('id', '!=', self.id)], limit=1)
        if partner_dup.identification_id:
            raise UserError('El cliente o proveedor ya se encuentra registrado con el Documento: %s'
                % (self.identification_id))
        else:
            return False

    # @api.onchange('company_type')
    # def change_country_id_partner(self):
    #     if self.company_type and self.company_type == 'person':
    #         self.country_id = 238
    #     elif self.company_type == 'company':
    #         self.country_id = False

    @api.onchange('people_type_company')
    def change_people_type_company(self):
        if self.company_type == 'company':
            if self.people_type_company == 'pjnd' and self.country_id == self.env.ref('base.ve'): 
                self.country_id = False

    @api.onchange('people_type_individual')
    def change_people_type_individual(self):
        if self.company_type == 'person':
            if self.people_type_individual == 'pnnr' and self.country_id == self.env.ref('base.ve'):
                self.country_id = False

    @staticmethod
    def validate_rif_er(str_rif):
        if str_rif:
            patron = r'^[VEJGC]-\d{7,8}-\d$'
            # Validar la cadena
            if re.match(patron, str_rif):
                return True
            else:
                raise UserError('El rif tiene el formato incorrecto. Ej: V-01234567-8, E-01234567-8, J-01234567-8 o G-01234567-8. Por favor verifique el formato y si posee los 12 caracteres como se indica en el Ej. e intente de nuevo')

    def validate_rif_duplicate(self, valor):
        if valor:
            partner_dup = self.search([('vat', '=', valor), ('id', '!=', self.id), ('parent_id', '=', False)],limit=1)
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