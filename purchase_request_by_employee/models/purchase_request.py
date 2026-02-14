from odoo import api, fields, models, exceptions, _

from lxml import etree
from odoo.exceptions import ValidationError
import json
from dateutil.relativedelta import relativedelta


class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Purchase Request"
    _order = 'date_order desc, id desc'

    
    name = fields.Char('Request Reference', required=True, index=True, copy=False, default='New')
    request_by = fields.Selection([('user', 'User'),('employee', 'Employee') ],default='user')
    date_order = fields.Datetime('Request Date', index=True, copy=False, default=fields.Datetime.now)
    approval_date = fields.Datetime('Approval date', readonly=True)
    date_approve = fields.Date('Approval Date', index=True, copy=False)
    partner_id = fields.Many2one('res.partner', string='Vendor')
    line_ids = fields.One2many('purchase.request.line', 'request_id', string='Request Lines',tracking=True)
    stage_id = fields.Many2one('purchase.request.stage', copy=False, string="Etapa", default=lambda self: self._get_stage_id(), tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1, order='id desc'))
    user_id = fields.Many2one('res.users', string='User', index=True, default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', 'Company', index=True,  default=lambda self: self.env.company.id)
    description = fields.Text('Description')
    purchase_ids = fields.One2many('purchase.order','request_id', string='Purchase Orders')
    approve_btn_visible = fields.Boolean(string="Approve Button Visible", compute='_btn_approve_compute')
    create_po_btn_visible = fields.Boolean(string="Approve Button Visible", compute='_btn_create_po_compute')
    purchase_order_count = fields.Integer(string='Purchase Order Count', compute='_compute_purchase_order_count')

    state = fields.Selection([
        ('draft', 'En Borrador'),
        ('approved', 'Aprobado'),
        ('done', 'Hecho'),
        ('cancelled', 'Rechazado')
    ], string='Estado', default='draft', tracking=True, copy=False)
    
    def _get_stage_id(self):
        default_stage = self.env['purchase.request.stage'].search([], limit=1, order='sequence')
        return default_stage
    
    @api.onchange('stage_id')
    def _btn_approve_compute(self):
        stage = self.stage_id
        groups = stage.group_ids
        flag = True

        if len(self.env['purchase.request.stage'].search([])) >= 1:
            flag = False
      
        if not flag and stage.final_stage:
            flag = True

        if not flag:
            ir_model_data_obj = self.env['ir.model.data'].sudo()
            group_name = ir_model_data_obj.search([('model', '=', 'res.groups'), ('res_id', 'in', groups.ids)])
            for grp in group_name.mapped('complete_name'):
                if not self.env.user.has_group(grp):
                    flag = True
                    break
                else:
                    flag = False

        self.approve_btn_visible = flag
        if self.state == 'cancelled':
            self.approve_btn_visible = True

    @api.onchange('stage_id')
    def _onchange_approval_date(self):
        if self.stage_id.final_stage and not self.stage_id.parent_id:
            self.approval_date = fields.Datetime.now()
        else:
            self.approval_date = False

    @api.onchange('stage_id')
    def _btn_create_po_compute(self):
        if len(self.purchase_ids) >= 1 :
            create_po = True
        else:
            create_po = self.stage_id.create_po
            if create_po:
                create_po = False
            else:
                create_po = True
        self.create_po_btn_visible = create_po

        if self.purchase_order_count > 0:
            self.state = 'done'
        
        if self.stage_id.final_stage and self.purchase_order_count == 0:
            self.state = 'approved'

    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_ids)
    
 

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if vals.get('company_id'):
                    vals['name'] = self.env['ir.sequence'].with_context(force_company=vals['company_id']).next_by_code('purchase.request') or _('New')
                else:
                    vals['name'] = self.env['ir.sequence'].next_by_code('purchase.request') or _('New')

        return super(PurchaseRequest, self).create(vals_list)

    
    def copy(self, default=None):
        new_pr = super(PurchaseRequest, self).copy(default=default)
        for line in new_pr.line_ids:
            seller = line.product_id._select_seller(
                partner_id=line.partner_id, quantity=line.product_qty,
                date=line.request_id.date_order and line.request_id.date_order.date(), uom_id=line.product_uom)
            line.date_planned = line._get_date_planned(seller)
        return new_pr

    
    def button_approve(self):
        if not self.stage_id.final_stage :
            self.stage_id =  self.stage_id.parent_id
        
        if self.stage_id.sequence > 1 and self.state != 'cancelled':
            self.state = 'approved'

        if self.stage_id.final_stage and not self.stage_id.parent_id:
            self.approval_date = fields.Datetime.now()
        else:
            self.approval_date = False
            
        self.get_view()
    
    def button_cancel(self):
        self.state = 'cancelled'
        self.stage_id = None
        self.get_view()
    
    def button_draft(self):
        self.state = 'draft'
        self.stage_id = self._get_stage_id()
        self.get_view()


    
    def action_view_purchase_order(self):
        action = self.env.ref('purchase.purchase_form_action').read()[0]
        if len(self.purchase_ids) > 1:
            action['domain'] = [('id','in',self.purchase_ids.ids)]
            action['views'] = [(self.env.ref('purchase.purchase_order_tree').id, 'tree')]
        else:
            action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            action['res_id'] = self.purchase_ids and self.purchase_ids[0].id 

        return action

    
    def create_po_btn(self):
        if not self.partner_id:
            raise ValidationError(_('Please Set Vendor in Request.'))

        if not self.line_ids:
            raise ValidationError(_('Please Create Request Line.'))

        if any (not line.product_id for line in self.line_ids):
            raise ValidationError('Please Set Product in %s'%','.join(self.line_ids.filtered(lambda r: not r.product_id).mapped('name')))

        po_obj = self.env['purchase.order']
        action = self.env.ref('purchase.purchase_form_action')
        result = action.read()[0]
        res = self.env.ref('purchase.purchase_order_form', False)
        result['views'] = [(res and res.id or False, 'form')]

        
        fiscal_position_id = self.env['account.fiscal.position'].sudo().with_context(company_id=self.company_id.id)._get_fiscal_position(self.partner_id)
        purchase_order = po_obj.create( {
            'partner_id': self.partner_id.id,
            'currency_id': self.partner_id.property_purchase_currency_id.id or self.env.user.company_id.currency_id.id,
            'payment_term_id': self.partner_id.property_supplier_payment_term_id.id,
            'fiscal_position_id': fiscal_position_id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'date_order': self.date_order,
            'request_id': self.id,
            
        })
        for line in self.line_ids:
            
            purchase_qty_uom = line.product_uom._compute_quantity(line.product_qty, line.product_id.uom_id)

            supplierinfo = line.product_id._select_seller(
                partner_id=purchase_order.partner_id,
                quantity=purchase_qty_uom,
                date=purchase_order.date_order and purchase_order.date_order.date(), 
                uom_id=line.product_id.uom_id
            )
            fpos = purchase_order.fiscal_position_id
            taxes = fpos.map_tax(line.product_id.supplier_taxes_id) if fpos else line.product_id.supplier_taxes_id
            if taxes:
                taxes = taxes.filtered(lambda t: t.company_id.id == self.company_id.id)

            # compute unit price
            price_unit = 0.0
            if supplierinfo:
                price_unit = self.env['account.tax'].sudo()._fix_tax_included_price_company(supplierinfo.price, line.product_id.supplier_taxes_id, taxes, self.company_id)
                if purchase_order.currency_id and supplierinfo.currency_id != purchase_order.currency_id:
                    price_unit = supplierinfo.currency_id._convert(price_unit, purchase_order.currency_id)

            # purchase line description in supplier lang
            supplierinfo_context = {}
            if supplierinfo and supplierinfo.partner_id.lang:
                supplierinfo_context['lang'] = supplierinfo.partner_id.lang
            if supplierinfo and supplierinfo.partner_id.id:
                supplierinfo_context['partner_id'] = supplierinfo.partner_id.id

            product_in_supplier_lang = line.product_id.with_context(supplierinfo_context)

            # name = '[%s] %s' % (line.product_id.default_code, product_in_supplier_lang.display_name)
            name = product_in_supplier_lang.display_name
            if product_in_supplier_lang.description_purchase:
                name += '\n' + product_in_supplier_lang.description_purchase

            po_order_line = self.env['purchase.order.line'].create( {
                'name': line.name,
                'product_qty': purchase_qty_uom,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_id.uom_id.id,
                'price_unit': price_unit,
                'order_id' : purchase_order.id,
                'date_planned': self.env['purchase.order.line']._get_date_planned(supplierinfo, purchase_order),
                'tax_ids': [(6, 0, taxes.ids)],
            })
        result['res_id'] = purchase_order.id or False
        return result


