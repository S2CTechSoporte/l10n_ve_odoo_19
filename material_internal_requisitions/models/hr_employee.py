# -*- coding: utf-8 -*-

from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    desti_loca_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        groups='material_internal_requisitions.group_requisition_user,material_internal_requisitions.group_requisition_manager,material_internal_requisitions.group_requisition_department',
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
