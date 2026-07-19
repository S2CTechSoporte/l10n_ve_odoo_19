# -*- coding: UTF-8 -*-
from odoo import _, fields, models, api
from odoo.exceptions import UserError
import re


RIF_FORMAT_ERROR = (
    'El rif tiene el formato incorrecto. Ej: V-01234567-8, E-01234567-8, '
    'J-01234567-8 o G-01234567-8. Por favor verifique el formato y si posee '
    'los 12 caracteres como se indica en el Ej. e intente de nuevo'
)
RIF_FORMAT_PATTERN = re.compile(
    r'[VEJGC](?:-\d{7,8}-\d|-\d{2}\.\d{3}\.\d{3}-\d|\d{8,9})'
)
BUSINESS_DOCUMENT_LOCK_FIELDS = {
    'vat',
    'rif',
    'identification_id',
    'name',
    'parent_id',
    'company_type',
    'country_id',
    'nationality',
}
BUSINESS_DOCUMENT_LOCK_FIELD_LABELS = {
    'vat': 'RIF',
    'rif': 'RIF',
    'identification_id': 'Documento de Identidad',
    'name': 'Nombre',
    'parent_id': 'Empresa relacionada',
    'company_type': 'Tipo de compañía',
    'country_id': 'País',
    'nationality': 'Tipo Documento',
}


def normalize_rif(value):
    return re.sub(r'[-.\s]', '', value or '').upper()


def is_valid_rif_format(value):
    return bool(RIF_FORMAT_PATTERN.fullmatch((value or '').strip().upper()))


def get_rif_search_values(value):
    normalized_rif = normalize_rif(value)
    if not normalized_rif:
        return []

    search_values = {value, normalized_rif}
    match = re.fullmatch(r'([VEJGC])(\d{7,8})(\d)', normalized_rif)
    if match:
        letter, number, digit = match.groups()
        search_values.add(f'{letter}-{number}-{digit}')
    return list(search_values)


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

    def _get_business_document_lock_reasons(self):
        self.ensure_one()
        reasons = []
        if self.sale_order_count > 0:
            reasons.append(_('Ventas: %(count)s', count=self.sale_order_count))
        if self.total_invoiced > 0:
            reasons.append(_('Facturado: %(amount)s', amount=self.total_invoiced))
        if self.purchase_order_count > 0:
            reasons.append(_('Compras: %(count)s', count=self.purchase_order_count))
        return reasons

    def _get_business_document_locked_field_labels(self, vals):
        locked_field_names = BUSINESS_DOCUMENT_LOCK_FIELDS.intersection(vals)
        changed_field_names = []
        for field_name in locked_field_names:
            field = self._fields[field_name]
            current_value = self[field_name]
            new_value = vals[field_name]
            if field.type == 'many2one':
                current_value = current_value.id or False
                new_value = new_value or False
            if current_value != new_value:
                changed_field_names.append(field_name)
        return [
            BUSINESS_DOCUMENT_LOCK_FIELD_LABELS.get(field_name, self._fields[field_name].string)
            for field_name in changed_field_names
        ]

    def _check_business_document_lock_before_write(self, vals):
        for partner in self.sudo():
            locked_field_labels = partner._get_business_document_locked_field_labels(vals)
            if not locked_field_labels:
                continue
            reasons = partner._get_business_document_lock_reasons()
            if reasons:
                raise UserError(_(
                    'No puede modificar los datos fiscales del contacto "%(partner)s" porque ya tiene ventas, facturas o compras registradas.\n'
                    'Campos bloqueados: %(fields)s.\n'
                    'Motivo: %(reasons)s.',
                    partner=partner.display_name,
                    fields=', '.join(locked_field_labels),
                    reasons=', '.join(reasons),
                ))

    def write(self, vals):
        if vals:
            self._check_business_document_lock_before_write(vals)
        return super().write(vals)

    @api.constrains('identification_id')
    def _check_identification_id(self):
        for partner in self:
            partner.validation_document_ident(partner.identification_id, partner.nationality)
            partner.validate_ci_duplicate(partner.identification_id)
            
    @api.constrains('rif')
    def _check_rif(self):
        for partner in self:
            if not partner.rif or partner.country_id.code != 'VE':
                continue
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

    @api.model
    def format_vat_ve(self, vat):
        return (vat or '').strip().upper()

    @api.model
    def _build_vat_error_message(self, country_code, wrong_vat, record_label):
        if country_code == 'VE' and is_valid_rif_format(wrong_vat):
            return '\n' + _(
                'El RIF [%(wrong_vat)s] para %(record_label)s no es válido. '
                'El formato es correcto, pero el dígito verificador no coincide. '
                'Revise que la letra, el número y el último dígito del RIF sean correctos.',
                wrong_vat=wrong_vat,
                record_label=record_label,
            )
        return super()._build_vat_error_message(country_code, wrong_vat, record_label)

            
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
            if is_valid_rif_format(str_rif):
                return True
            raise UserError(RIF_FORMAT_ERROR)

    def validate_rif_duplicate(self, valor):
        if valor:
            partner_dup = self.search([('vat', 'in', get_rif_search_values(valor)), ('id', '!=', self.id), ('parent_id', '=', False)],limit=1)
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