from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    state_id = fields.Many2one(
        comodel_name="res.country.state",
        related="partner_id.state_id",
        string="Zone",
        store=True,
        readonly=True,
        index=True,
    )