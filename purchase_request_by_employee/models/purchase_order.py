from odoo import api, fields, models, exceptions, _

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    request_id = fields.Many2one('purchase.request', string='Purchase Request')