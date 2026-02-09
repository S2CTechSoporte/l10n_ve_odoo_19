# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInternalRequisitionCreate(TransactionCase):
    def setUp(self):
        super().setUp()
        Employee = self.env['hr.employee'].sudo()
        self.employee = Employee.search([('user_id', '=', self.env.user.id)], limit=1)

        if not self.employee:
            self.department = self.env['hr.department'].sudo().create({'name': 'Test Department'})
            self.employee = Employee.create({
                'name': 'Test Employee',
                'user_id': self.env.user.id,
                'department_id': self.department.id,
                'work_email': 'employee@example.com',
            })
        else:
            self.department = self.employee.department_id
            if not self.department:
                self.department = self.env['hr.department'].sudo().create({'name': 'Test Department'})
                self.employee.department_id = self.department.id

        if not self.employee.work_email:
            self.employee.work_email = 'employee@example.com'

        self.manager = Employee.create({
            'name': 'Test Manager',
            'work_email': 'manager@example.com',
            'department_id': self.department.id,
        })
        if hasattr(self.department, 'manager_id'):
            self.department.manager_id = self.manager.id

    def test_create_multi_assigns_sequence_name(self):
        Requisition = self.env['internal.requisition'].sudo()

        requisitions = Requisition.create([
            {
                'request_emp': self.employee.id,
                'department_id': self.department.id,
                'company_id': self.env.company.id,
            },
            {
                'request_emp': self.employee.id,
                'department_id': self.department.id,
                'company_id': self.env.company.id,
            },
        ])

        self.assertEqual(len(requisitions), 2)
        self.assertTrue(requisitions[0].name)
        self.assertTrue(requisitions[1].name)
        self.assertNotEqual(requisitions[0].name, requisitions[1].name)

    def test_requisition_confirm_does_not_fail_on_lang(self):
        confirm_tmpl = self.env.ref('material_internal_requisitions.email_confirm_irrequisition')
        ir_user_tmpl = self.env.ref('material_internal_requisitions.email_ir_requisition')
        dept_approved_tmpl = self.env.ref('material_internal_requisitions.email_internal_requisition_iruser_custom')

        self.assertEqual(confirm_tmpl.email_layout_xmlid, 'mail.mail_notification_light')
        self.assertEqual(ir_user_tmpl.email_layout_xmlid, 'mail.mail_notification_light')
        self.assertEqual(dept_approved_tmpl.email_layout_xmlid, 'mail.mail_notification_light')

        Requisition = self.env['internal.requisition'].sudo()
        requisition = Requisition.create({
            'request_emp': self.employee.id,
            'department_id': self.department.id,
            'company_id': self.env.company.id,
        })

        requisition.requisition_confirm()

        self.assertEqual(requisition.state, 'confirm')

        mails = self.env['mail.mail'].sudo().search([
            ('model', '=', requisition._name),
            ('res_id', '=', requisition.id),
        ], order='id desc')
        self.assertTrue(mails, 'Expected at least one outgoing email to be queued')

        mail = mails[0]
        body = mail.body_html or ''
        self.assertIn('background-color: #F1F1F1', body)
        self.assertNotIn('#8E0000', body)
        self.assertNotIn('${', body)
        self.assertNotIn('{{', body)
        self.assertNotIn('{%', body)
        self.assertNotIn('<t ', body)
        self.assertIn(f'/web#id={requisition.id}', body)
