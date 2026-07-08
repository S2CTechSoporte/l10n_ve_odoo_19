# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError
from markupsafe import Markup


class StockPicking(models.Model):
    _inherit = "stock.picking"

    name_driver = fields.Char(string="Conductor")
    identification_driver = fields.Char(string="Cédula")

    vehicle = fields.Char(string="Vehículo")
    license_plate = fields.Char(string="Placa")
    vehicle_brand = fields.Char(string="Marca")
    vehicle_type = fields.Char(string="Tipo")

    total_destination_packages = fields.Integer(
        string='Total Bultos = ', compute='_compute_total_destination_packages', store=False)

    def action_print_label_bags(self):
        self.ensure_one()
        if not self.move_line_ids:
            raise UserError("No hay líneas de movimiento en este picking.")

        return self.env.ref('s2c_stockpicking_report.action_print_label_bags_label_4x7').report_action(self)

    @api.depends('move_line_ids.result_package_id')
    def _compute_total_destination_packages(self):
        for picking in self:
            unique_packages = set(line.result_package_id.id for line in picking.move_line_ids if line.result_package_id)
            picking.total_destination_packages = len(unique_packages)


    def company_vat_raw(self):
        return Markup(self.company_id.vat or '')

    def origin_raw(self):
        return Markup(self.origin or '')

    def state_name_raw(self):
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
            'À': 'A', 'È': 'E', 'Ì': 'I', 'Ò': 'O', 'Ù': 'U',
            'Ä': 'A', 'Ë': 'E', 'Ï': 'I', 'Ö': 'O', 'Ü': 'U',
            'ñ': 'n', 'Ñ': 'N',
        }
        state_name = (self.state_id.name or '').upper()
        for key, value in replacements.items():
            state_name = state_name.replace(key, value)
        return Markup(state_name)

    def partner_name_raw(self):
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
            'À': 'A', 'È': 'E', 'Ì': 'I', 'Ò': 'O', 'Ù': 'U',
            'Ä': 'A', 'Ë': 'E', 'Ï': 'I', 'Ö': 'O', 'Ü': 'U',
            'ñ': 'n', 'Ñ': 'N',
        }
        partner_name = (self.partner_id.name or '').upper()
        for key, value in replacements.items():
            partner_name = partner_name.replace(key, value)
        return Markup(partner_name)
