from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.constrains('price_unit')
    def _check_price_unit(self):
        for line in self:
            if line.price_unit <= 0:
                raise ValidationError("El precio unitario no puede ser cero o negativo en las líneas de la orden de venta.")
