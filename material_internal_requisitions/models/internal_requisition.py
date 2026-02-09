# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime,date
from odoo.exceptions import UserError

class InternalRequisition(models.Model):
    _name = 'internal.requisition'
    _description = 'Internal Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']      #   odoo11
    _order = 'id desc'
    
    #@api.multi
    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancel', 'reject'):
                raise UserError(_('You can not delete Internal Requisition which is not in draft or cancelled or rejected state.'))
        return super(InternalRequisition, self).unlink()
    
    name = fields.Char(
        string='Number',
        index=True,
        readonly=True,
    )
    state = fields.Selection([
        ('draft', 'New'),
        ('confirm', 'Waiting Department Approval'),
        ('manager', 'Waiting IR Approved'),
        ('user', 'Approved'),
        ('stock', 'Requested Stock'),
        ('receive', 'Received'),
        ('cancel', 'Cancelled'),
        ('reject', 'Rejected')],
        default='draft',
        tracking=True,
    )
    request_date = fields.Date(
        string='Requisition Date',
        default=fields.Date.today(),
        required=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        required=True,
        copy=True,
        #related='request_emp.department_id',
    )
    request_emp = fields.Many2one(
        'hr.employee',
        string='Employee',
        default=lambda self: self._get_current_employee(),
        required=True,
        copy=True,
    )
    approve_manager = fields.Many2one(
        'hr.employee',
        string='Department Manager',
        readonly=True,
        copy=False,
    )
    reject_manager = fields.Many2one(
        'hr.employee',
        string='Department Manager Reject',
        readonly=True,
    )
    approve_user = fields.Many2one(
        'hr.employee',
        string='Approved by',
        readonly=True,
        copy=False,
    )
    reject_user = fields.Many2one(
        'hr.employee',
        string='Rejected by',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        #related='request_emp.company_id',
        default=lambda self: self.env.user.company_id,
        required=True,
        copy=True,
    )
    location = fields.Many2one(
        'stock.location',
        string='Source Location',
        #required=True,
        copy=True,
    )
    requisition_line_ids = fields.One2many(
        'custom.internal.requisition.line',
        'requisition_id',
        string='Requisitions Line',
        copy=True,
    )
    date_end = fields.Date(
        string='Requisition Deadline', 
        readonly=True,
        help='Last date for the product to be needed',
        copy=True,
    )
    date_done = fields.Date(
        string='Date Done', 
        readonly=True, 
        help='Date of Completion of Internal Requisition',
    )
    managerapp_date = fields.Date(
        string='Department Approval Date',
        #default=fields.Date.today(),
        readonly=True,
        copy=False,
    )
    manareject_date = fields.Date(
        string='Department Manager Reject Date',
        #default=fields.Date.today(),
        readonly=True,
    )
    userreject_date = fields.Date(
        string='Rejected Date',
        #default=fields.Date.today(),
        readonly=True,
        copy=False,
    )
    userrapp_date = fields.Date(
        string='Approved Date',
        #default=fields.Date.today(),
        readonly=True,
        copy=False,
    )
    receive_date = fields.Date(
        string='Received Date',
        #default=fields.Date.today(),
        readonly=True,
        copy=False,
    )
    reason = fields.Text(
        string='Reason for Requisitions',
        required=False,
        copy=True,
    )
    account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        copy=True,
    )
    desti_loca_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        required=False,
        copy=True,
    )
    delivery_picking_id = fields.Many2one(
        'stock.picking',
        string='Internal Picking',
        readonly=True,
        copy=False,
    )
    requisiton_responsible_id = fields.Many2one(
        'hr.employee',
        string='Requisition Responsible',
        copy=True,
    )
    confirm_id = fields.Many2one(
        'hr.employee',
        string='Confirmed by',
        readonly=True,
        copy=False,
    )
    confirm_date = fields.Date(
        string='Confirmed Date',
        #default=fields.Date.today(),
        readonly=True,
        copy=False,
    )
    custom_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string='Picking Type',
        copy=False,
    )

    def init(self):
        super().init()
        self._fix_legacy_mail_templates()

    @api.model
    def _fix_legacy_mail_templates(self):
        module = 'material_internal_requisitions'

        xmlids = [
            f'{module}.email_confirm_irrequisition',
            f'{module}.email_ir_requisition',
            f'{module}.email_internal_requisition_iruser_custom',
        ]

        Imd = self.env['ir.model.data'].sudo()
        imd_recs = Imd.search([
            ('module', '=', module),
            ('name', 'in', [
                'email_confirm_irrequisition',
                'email_ir_requisition',
                'email_internal_requisition_iruser_custom',
            ]),
            ('model', '=', 'mail.template'),
        ])
        if imd_recs:
            imd_recs.write({'noupdate': False})

        values_by_xmlid = {
            f'{module}.email_confirm_irrequisition': {
                'email_from': "{{ object.request_emp.work_email }}",
                'subject': "Request for Internal Requisition - {{ object.name }}",
                'subject_es_VE': "Solicitud de requisición interna - {{ object.name }}",
                'email_to': "{{ object.request_emp.parent_id.sudo().work_email or object.request_emp.department_id.sudo().manager_id.work_email }}",
                'lang': "{{ object.request_emp.user_id.lang or user.lang }}",
                'email_layout_xmlid': 'mail.mail_notification_light',
                'body_html_en': """
<p>Dear <t t-out="object.request_emp.parent_id.sudo().name or object.request_emp.department_id.sudo().manager_id.name"/>,</p>

<p>You have a new internal requisition request awaiting your approval:</p>
<ul>
    <li><strong>Requisition</strong>: <t t-out="object.name"/></li>
    <li><strong>Requested by</strong>: <t t-out="object.request_emp.name"/></li>
    <li><strong>Department</strong>: <t t-out="object.request_emp.department_id.name or ''"/></li>
</ul>

<t t-set="base_url" t-value="env['ir.config_parameter'].sudo().get_param('web.base.url')"/>
<p>
    <a t-att-href="'%s/web#id=%s&model=%s&view_type=form' % (base_url, object.id, object._name)">Open in Odoo</a>
</p>
""".strip(),
                'body_html_es_VE': """
<p>Estimado/a <t t-out="object.request_emp.parent_id.sudo().name or object.request_emp.department_id.sudo().manager_id.name"/>,</p>

<p>Tiene una nueva requisición interna pendiente por su aprobación:</p>
<ul>
    <li><strong>Requisición</strong>: <t t-out="object.name"/></li>
    <li><strong>Solicitada por</strong>: <t t-out="object.request_emp.name"/></li>
    <li><strong>Departamento</strong>: <t t-out="object.request_emp.department_id.name or ''"/></li>
</ul>

<t t-set="base_url" t-value="env['ir.config_parameter'].sudo().get_param('web.base.url')"/>
<p>
    <a t-att-href="'%s/web#id=%s&model=%s&view_type=form' % (base_url, object.id, object._name)">Abrir en Odoo</a>
</p>
""".strip(),
            },
            f'{module}.email_ir_requisition': {
                'email_from': "{{ object.request_emp.work_email }}",
                'subject': "Approval Request for Internal Requisition to IR User - {{ object.name }}",
                'subject_es_VE': "Solicitud de aprobación de requisición interna al usuario IR - {{ object.name }}",
                'email_to': "{{ object.requisiton_responsible_id.work_email }}",
                'lang': "{{ object.requisiton_responsible_id.user_id.lang or user.lang }}",
                'email_layout_xmlid': 'mail.mail_notification_light',
                'body_html_en': """
<p>Dear <t t-out="object.requisiton_responsible_id.name"/>,</p>

<p>An internal requisition has been submitted and requires your approval:</p>
<ul>
    <li><strong>Requisition</strong>: <t t-out="object.name"/></li>
    <li><strong>Requested by</strong>: <t t-out="object.request_emp.name"/></li>
    <li><strong>Department</strong>: <t t-out="object.request_emp.department_id.name or ''"/></li>
</ul>

<t t-set="base_url" t-value="env['ir.config_parameter'].sudo().get_param('web.base.url')"/>
<p>
    <a t-att-href="'%s/web#id=%s&model=%s&view_type=form' % (base_url, object.id, object._name)">Open in Odoo</a>
</p>
""".strip(),
                'body_html_es_VE': """
<p>Estimado/a <t t-out="object.requisiton_responsible_id.name"/>,</p>

<p>Se ha registrado una requisición interna y requiere su aprobación:</p>
<ul>
    <li><strong>Requisición</strong>: <t t-out="object.name"/></li>
    <li><strong>Solicitada por</strong>: <t t-out="object.request_emp.name"/></li>
    <li><strong>Departamento</strong>: <t t-out="object.request_emp.department_id.name or ''"/></li>
</ul>

<t t-set="base_url" t-value="env['ir.config_parameter'].sudo().get_param('web.base.url')"/>
<p>
    <a t-att-href="'%s/web#id=%s&model=%s&view_type=form' % (base_url, object.id, object._name)">Abrir en Odoo</a>
</p>
""".strip(),
            },
            f'{module}.email_internal_requisition_iruser_custom': {
                'email_from': "{{ object.approve_manager.work_email }}",
                'subject': "Department Approval Internal Requisition - {{ object.name }}",
                'subject_es_VE': "Aprobación de departamento para requisición interna - {{ object.name }}",
                'email_to': "{{ object.request_emp.work_email }}",
                'lang': "{{ object.request_emp.user_id.lang or user.lang }}",
                'email_layout_xmlid': 'mail.mail_notification_light',
                'body_html_en': """
<p>Dear <t t-out="object.request_emp.name"/>,</p>

<p>Your internal requisition has been approved by your department:</p>
<ul>
    <li><strong>Requisition</strong>: <t t-out="object.name"/></li>
    <li><strong>Approved by</strong>: <t t-out="object.approve_manager.name"/></li>
</ul>

<t t-set="base_url" t-value="env['ir.config_parameter'].sudo().get_param('web.base.url')"/>
<p>
    <a t-att-href="'%s/web#id=%s&model=%s&view_type=form' % (base_url, object.id, object._name)">Open in Odoo</a>
</p>
""".strip(),
                'body_html_es_VE': """
<p>Estimado/a <t t-out="object.request_emp.name"/>,</p>

<p>Su requisición interna ha sido aprobada por su departamento:</p>
<ul>
    <li><strong>Requisición</strong>: <t t-out="object.name"/></li>
    <li><strong>Aprobada por</strong>: <t t-out="object.approve_manager.name"/></li>
</ul>

<t t-set="base_url" t-value="env['ir.config_parameter'].sudo().get_param('web.base.url')"/>
<p>
    <a t-att-href="'%s/web#id=%s&model=%s&view_type=form' % (base_url, object.id, object._name)">Abrir en Odoo</a>
</p>
""".strip(),
            },
        }

        for xmlid, values in values_by_xmlid.items():
            template = self.env.ref(xmlid, raise_if_not_found=False)
            if not template:
                continue

            def _has_legacy_body(lang_code):
                body = (template.with_context(lang=lang_code).body_html or '')
                return any(token in body for token in ('${', '% if', '{%', '{{', '#8E0000'))

            langs_to_check = ['en_US']
            if self.env['res.lang']._get_data(code='es_VE'):
                langs_to_check.append('es_VE')

            legacy_body_langs = [
                lang_code
                for lang_code in langs_to_check
                if _has_legacy_body(lang_code)
            ]

            legacy_subject_langs = [
                lang_code
                for lang_code in langs_to_check
                if '${' in (template.with_context(lang=lang_code).subject or '')
            ]

            needs_fix = any(
                isinstance(getattr(template, key, False), str) and '${' in getattr(template, key)
                for key in ('lang', 'subject', 'email_from', 'email_to')
            )
            needs_fix = needs_fix or (isinstance(template.lang, str) and template.lang.strip() == '${object.lang}')
            needs_fix = needs_fix or bool(legacy_body_langs) or bool(legacy_subject_langs)

            if values.get('email_layout_xmlid') and template.email_layout_xmlid != values['email_layout_xmlid']:
                needs_fix = True

            if needs_fix:
                write_vals = {
                    key: val
                    for key, val in values.items()
                    if key not in ('body_html_en', 'body_html_es_VE', 'subject_es_VE')
                }
                template.sudo().write(write_vals)

                if values.get('subject_es_VE') and 'es_VE' in legacy_subject_langs:
                    template.with_context(lang='es_VE').sudo().write({'subject': values['subject_es_VE']})

                if 'body_html_en' in values and 'en_US' in legacy_body_langs:
                    template.with_context(lang='en_US').sudo().write({'body_html': values['body_html_en']})
                if 'body_html_es_VE' in values and 'es_VE' in legacy_body_langs:
                    template.with_context(lang='es_VE').sudo().write({'body_html': values['body_html_es_VE']})
    
    @api.model_create_multi
    def create(self, vals_list):
        SEQUENCE_CODE = 'internal.requisition.seq'

        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        IrSequence = self.env['ir.sequence']
        ResCompany = self.env['res.company']

        for vals in vals_list:
            if vals.get('name'):
                continue

            company = (
                ResCompany.browse(vals.get('company_id'))
                if vals.get('company_id')
                else self.env.company
            )
            company = company or self.env.company

            seq = IrSequence.with_company(company)
            name = seq.next_by_code(SEQUENCE_CODE)

            if not name:
                seq.sudo().create({
                    'prefix': 'IR',
                    'name': SEQUENCE_CODE,
                    'code': SEQUENCE_CODE,
                    'implementation': 'standard',
                    'padding': 5,
                    'number_increment': 1,
                    'company_id': company.id,
                })
                name = seq.next_by_code(SEQUENCE_CODE)

            vals['name'] = name

        return super(InternalRequisition, self).create(vals_list)
        
    #@api.multi
    def requisition_confirm(self):
        for rec in self:
            manager_mail_template = self.env.ref('material_internal_requisitions.email_confirm_irrequisition')
            rec.confirm_id = rec.request_emp.id
            rec.confirm_date = fields.Date.today()
            rec.state = 'confirm'
            if manager_mail_template:
                manager_mail_template.send_mail(self.id)
            
    #@api.multi
    def requisition_reject(self):
        for rec in self:
            rec.state = 'reject'
            rec.reject_user = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            rec.userreject_date = fields.Date.today()

    #@api.multi
    def manager_approve(self):
        for rec in self:
            rec.managerapp_date = fields.Date.today()
            rec.approve_manager = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            employee_mail_template = self.env.ref('material_internal_requisitions.email_internal_requisition_iruser_custom')
            email_iruser_template = self.env.ref('material_internal_requisitions.email_ir_requisition')
            employee_mail_template.sudo().send_mail(self.id)
            email_iruser_template.sudo().send_mail(self.id)
            rec.state = 'manager'

    #@api.multi
    def user_approve(self):
        for rec in self:
            rec.userrapp_date = fields.Date.today()
            rec.approve_user = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
            rec.state = 'user'

    #@api.multi
    def reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    #@api.multi
    def request_stock(self):
        
        stock_obj = self.env['stock.picking']
        move_obj = self.env['stock.move']
        #internal_obj = self.env['stock.picking.type'].search([('code','=', 'internal')])
#         internal_obj = self.env['stock.picking.type'].search([('usage','=', 'internal')], limit=1)
#         if not internal_obj:
#             raise UserError(_('Please configure Internal Picking Type under Inventory.'))
        for rec in self:
            if not rec.location:
                raise UserError(_('Select Source Location under the picking details.'))
            
            if not rec.custom_picking_type_id:
                raise UserError(_('Select Picking Type under the picking details.'))

            if not rec.desti_loca_id:
                raise UserError(_('Select Destination Location under the picking details.'))
            #if not rec.request_emp.desti_loca_id or not rec.request_emp.department_id.desti_loca_id:
             #   raise Warning(_('Select Destination Location under the picking details.'))
            vals = {
                'partner_id' : rec.request_emp.sudo().address_id.id,
                # 'min_date' : fields.Date.today(), #odoo13
                'location_id' : rec.location.id,
                #'location_dest_id' : rec.desti_loca_id.id,
                'location_dest_id' : rec.desti_loca_id and rec.desti_loca_id.id or rec.request_emp.sudo().desti_loca_id.id or rec.request_emp.sudo().department_id.desti_loca_id.id,
                'picking_type_id' : rec.custom_picking_type_id.id, #internal_obj.id,
                'name' :  '%s/%s'  % (rec.name, rec.custom_picking_type_id.name), #internal_obj.name,
                'note' : rec.reason,
                'inter_requi_id' : rec.id,
                'origin' : rec.name,
                'company_id' : rec.company_id.id,
            }
            stock_id = stock_obj.create(vals)
            for line in rec.requisition_line_ids:
            
                vals1 = {
                    'product_id' : line.product_id.id,
                    'product_uom_qty' : line.qty,
                    'product_uom' : line.uom.id,
                    'location_id' : rec.location.id,
                    'location_dest_id' : rec.request_emp.desti_loca_id.id,
                    'name' : line.description,
                    'picking_id' : stock_id.id,
                    'company_id' : line.requisition_id.company_id.id,
                }
                move_id = move_obj.create(vals1)
            vals3 = {
                'delivery_picking_id' : stock_id.id,
            }
            rec.write(vals3)
            rec.state = 'stock'
    
    #@api.multi
    def action_received(self):
        for rec in self:
            rec.receive_date = fields.Date.today()
            rec.state = 'receive'
    
    #@api.multi
    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'
    
#     @api.multi
#     def action_done(self):
#         for rec in self:
#             rec.state = 'done'
            
    @api.onchange('request_emp')
    def set_department(self):
        for rec in self:
            rec.department_id = rec.request_emp.sudo().department_id.id
            rec.desti_loca_id = rec.request_emp.desti_loca_id.id or rec.request_emp.department_id.desti_loca_id.id 
            
    #@api.multi
    def show_picking(self):
#        for rec in self:
        self.ensure_one()
        res = self.env.ref('stock.action_picking_tree_all')
        res = res.read()[0]
        res['domain'] = str([('inter_requi_id','=',self.id)])
        return res
    
    def _get_current_employee(self):
        #resource = self.env['resource.resource'].search([('user_id', '=', self.env.user.id)])
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        return employee
   

    def _get_current_subordinates(self):
            employee = self._get_current_employee()
            return employee.child_ids

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
