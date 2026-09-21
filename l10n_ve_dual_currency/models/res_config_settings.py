from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fcurrency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.fcurrency_id",
        string="Reference Currency",
        readonly=False,
    )
