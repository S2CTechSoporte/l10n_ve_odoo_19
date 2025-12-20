# coding: utf-8
from odoo import models, fields, api, exceptions, _


class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    def _get_sequence_code(self):
        # metodo que crea la secuencia 

        if self.journal_id.nro_ctrl_sequence_id:
            self.nro_ctrl = self.journal_id.nro_ctrl_sequence_id.next_by_id()
            return self.nro_ctrl
        else:    
            return super()._get_sequence_code()
    
    def _compute_name(self):
        super()._compute_name()
        for move in self:
            if move.journal_id.nro_ctrl_sequence_id and not move.nro_ctrl:
                move.nro_ctrl = move.journal_id.nro_ctrl_sequence_id.next_by_id()