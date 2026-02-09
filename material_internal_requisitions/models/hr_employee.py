# -*- coding: utf-8 -*-

from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    desti_loca_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        help='This field is used to set the default destination location for the employee when creating material internal requisitions.')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
