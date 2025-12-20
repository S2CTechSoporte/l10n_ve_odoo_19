from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IrSequence(models.Model):
    
    _inherit = 'ir.sequence'
    number_final = fields.Integer(
        string='Numero Final',
        help="Si quieres controlar el final de la secuencia coloca el ultimo numero justo aqui",
        default=None)
    
    def get_next_char(self, number_next):

        if self.number_final:
            if isinstance(number_next, tuple):
                number_nxt = number_next[0]
            else:
                number_nxt = number_next
                
            if number_nxt > self.number_final:
                raise UserError("Por favor actualice el rango de la secuencia del número de control")
        
        return super().get_next_char(number_next)

