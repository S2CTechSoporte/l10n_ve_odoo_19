from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    state_id = fields.Many2one(
        comodel_name="res.country.state",
        related="partner_id.state_id",
        string="Zone",
        store=True,
        readonly=True,
        index=True,
    )