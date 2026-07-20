# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestInternalRequisitionCreate(TransactionCase):
    def setUp(self):
        super().setUp()
        Employee = self.env['hr.employee'].sudo()
        self.employee = Employee.search([('user_id', '=', self.env.user.id)], limit=1)
        self.source_location = self.env.ref('stock.stock_location_stock')
        self.destination_location = self.env['stock.location'].sudo().create({
            'name': 'Test Requisition Destination',
            'location_id': self.source_location.id,
            'usage': 'internal',
        })
        self.picking_type = self.env['stock.picking.type'].sudo().search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        self.product = self.env['product.product'].sudo().create({
            'name': 'Test Requisition Product',
            'type': 'consu',
        })
        self.analytic_account = self.env['account.analytic.account'].sudo().create({
            'name': 'Test Requisition Analytic Account',
            'plan_id': self.env.ref('analytic.analytic_plan_projects').id,
            'company_id': self.env.company.id,
        })

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

        self.employee.desti_loca_id = self.destination_location.id
        self.employee.account_id = self.analytic_account.id

        self.manager = Employee.create({
            'name': 'Test Manager',
            'work_email': 'manager@example.com',
            'department_id': self.department.id,
        })
        if hasattr(self.department, 'manager_id'):
            self.department.manager_id = self.manager.id

    def test_request_stock_uses_description_picking_on_moves(self):
        Requisition = self.env['internal.requisition'].sudo()

        requisition = Requisition.create({
            'request_emp': self.employee.id,
            'department_id': self.department.id,
            'company_id': self.env.company.id,
            'location': self.source_location.id,
            'desti_loca_id': self.destination_location.id,
            'custom_picking_type_id': self.picking_type.id,
            'requisition_line_ids': [
                (0, 0, {
                    'product_id': self.product.id,
                    'description': 'Custom move description',
                    'qty': 2.0,
                    'uom': self.product.uom_id.id,
                }),
            ],
        })

        requisition.request_stock()

        self.assertEqual(requisition.state, 'stock')
        self.assertTrue(requisition.delivery_picking_id)

        move = requisition.delivery_picking_id.move_ids
        self.assertEqual(len(move), 1)
        self.assertEqual(move.description_picking, 'Custom move description')
        self.assertEqual(move.reference, requisition.delivery_picking_id.name)

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

    def test_request_employee_onchange_sets_default_analytic_account(self):
        requisition = self.env['internal.requisition'].new({
            'request_emp': self.employee.id,
        })

        requisition.set_department()

        self.assertEqual(requisition.department_id, self.employee.department_id)
        self.assertEqual(requisition.account_id, self.employee.account_id)
        self.assertEqual(requisition.desti_loca_id, self.employee.desti_loca_id)

    def test_location_onchange_sets_first_warehouse_picking_type(self):
        warehouse = self.source_location.warehouse_id
        expected_picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', warehouse.id),
        ], limit=1)
        self.assertTrue(expected_picking_type)

        requisition = self.env['internal.requisition'].new({
            'location': self.source_location.id,
        })

        requisition._onchange_location()

        self.assertEqual(requisition.location_warehouse_id, warehouse)
        self.assertEqual(requisition.custom_picking_type_id, expected_picking_type)
