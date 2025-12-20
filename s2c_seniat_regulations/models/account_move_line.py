from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # @api.constrains('price_unit')
    # def _check_price_unit(self):
    #     for line in self:
    #         if line.price_unit <= 0 and line.move_id.move_type in ['out_invoice', 'in_invoice']:
    #             raise ValidationError("El precio unitario no puede ser cero o negativo en las líneas de la factura.")
