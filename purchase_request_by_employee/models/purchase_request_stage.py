from odoo import api, fields, models, exceptions, _

class PurchaseRequestStage(models.Model):
    _name = "purchase.request.stage"
    _description = "Purchase Requisition Stage"
    _order = "sequence"

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(default=1)
    create_po = fields.Boolean(string='Create PO', default=False)
    final_stage = fields.Boolean(string='Final Stage', default=False)
    parent_id = fields.Many2one('purchase.request.stage', string='Next Stage', help='Will Move to Selected Stage')
    group_ids = fields.Many2many('res.groups', string='Approval Groups', help='Approval From Selected Group')

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot set recursion stage.'))