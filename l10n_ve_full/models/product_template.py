# coding: utf-8
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    concept_id = fields.Many2one(
            'account.wh.islr.concept', 'Concepto de retención ISLR', required=False,
            help="Concepto Retención de Renta a aplicar al servicio")

    @api.onchange('type')
    def _onchange_type(self):
        res = super(ProductTemplate, self)._onchange_type()
        concept_id = False
        if self.type == 'service':
            concept_obj = self.env['account.wh.islr.concept']

            concept_id = concept_obj.search([('withholdable', '=', False)])
            concept_id = concept_id and concept_id[0] or False
            if not concept_id:
                raise UserError("Invalid action! \nDebe crear el concepto de retención de ingresos")
            res['concept_id'] = concept_id or False
        return res

    @api.constrains('default_code')
    def _check_default_code(self):
        for record in self:
            if record.default_code:
                domain = [('default_code', '=', record.default_code), ('id', '!=',record.id  )]
                
                if self.env['product.template'].search(domain, limit=1):
                    raise UserError( _("La referencia interna '%s' ya existe.", record.default_code) )
        
    @api.onchange('default_code')
    def _onchange_default_code(self):
        # deshabilita la comprobacion original para que solo use
        # _check_default_code
        pass