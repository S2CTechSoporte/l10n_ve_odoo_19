# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    custom_sequence_id = fields.Many2one('ir.sequence', 'Secuencia de diario o factura', help="Secuencia personalizada de Factura", copy=False)
    nro_ctrl_sequence_id = fields.Many2one('ir.sequence', 'Secuencia Num. Ctrl.', help="Secuencia personalizada de Factura", copy=False)
    number_initial = fields.Integer(string='Inicio Nro de ctrl', related='nro_ctrl_sequence_id.number_next_actual', copy=False, readonly=False)    
    number_final = fields.Integer(string='Fin Nro de ctrl', related='nro_ctrl_sequence_id.number_final', copy=False, readonly=False)


    def write(self, values):
        super().write(values)
        self.nro_ctrl_sequence_id.write(
            {
                'prefix': '00-',
                'padding': 7 
             }
        )
