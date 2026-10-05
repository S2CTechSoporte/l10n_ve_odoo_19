from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    secondary_currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.secondary_currency_id",
        string="Reference Currency",
        readonly=False,
    )
