from odoo import api, fields, models, exceptions, _

class PurchaseRequestLine(models.Model):
    _name = 'purchase.request.line'
    _description = 'Purchase Request Line'

    name = fields.Text(string='Description')
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure', tracking=True)
    product_uom = fields.Many2one('uom.uom', string='Product Unit of Measure', tracking=True)
    product_id = fields.Many2one('product.product', string='Product', domain=[('purchase_ok', '=', True)], change_default=True, tracking=True)
    
    product_type = fields.Selection(related='product_id.type', tracking=True)
    request_id = fields.Many2one('purchase.request', string='Request Reference', index=True, ondelete='cascade', tracking=True)
    company_id = fields.Many2one('res.company', related='request_id.company_id', string='Company', store=True, tracking=True)
    stage_id = fields.Many2one(related='request_id.stage_id', store=True, tracking=True)
    partner_id = fields.Many2one('res.partner', related='request_id.partner_id', string='Partner', store=True, tracking=True)
    date_order = fields.Datetime(related='request_id.date_order', string='Request Date', readonly=True, tracking=True)

    @api.onchange('product_id')
    def onchange_product_id(self):
        result = {}
        if not self.product_id:
            return result

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        product_lang = self.product_id.with_context(
            lang=self.partner_id.lang,
            partner_id=self.partner_id.id,
        )
        self.name = product_lang.display_name
        if product_lang.description_purchase:
            self.name += '\n' + product_lang.description_purchase


        return result