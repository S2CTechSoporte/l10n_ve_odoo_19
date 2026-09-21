from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    fcurrency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Reference Currency",
        default=lambda self: self.env.ref("base.USD"),
        help="Secondary currency used to display Venezuelan accounting amounts.",
    )
