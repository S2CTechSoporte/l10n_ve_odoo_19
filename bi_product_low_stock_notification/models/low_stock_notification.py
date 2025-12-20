# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields,models,api, _
from ast import literal_eval
from odoo import SUPERUSER_ID
import base64

class LowStockNotification(models.Model):
	_name="low.stock.notification"
	_description="Low Stock Notification"

	company_id = fields.Many2one('res.company','Company')
	low_stock_products_ids = fields.One2many(related='company_id.low_stock_products_ids',string="Low Stock")

	def action_list_products_(self):

		products_list=[]
		
		products_dlt = [(2,dlt.id,0)for dlt in self.env.company.low_stock_products_ids]
		self.env.company.low_stock_products_ids = products_dlt
	
		if self.env.company.notification_base == 'on_hand':
			if self.env.company.notification_products == 'for_all':

				if self.env.company.notification_product_type == 'variant':
					result = self.env['product.product'].search([('qty_available','<',self.env.company.min_quantity),
															   ('detailed_type','=','product')])
					for product in result:
						name_att = ' '
						for attribute in product.product_template_attribute_value_ids:
						  name_att = name_att  +  attribute.name + '  '

						name_pro = ' '
						if product.product_template_attribute_value_ids :
						  name_pro = product.name + ' - ' +name_att + '  '
						else :
						  name_pro = product.name

						products_list.append([0,0,{'name':name_pro,
											  'limit_quantity':self.env.company.min_quantity,
											  'stock_quantity':product.qty_available,
											 }])

				else:
					result = self.env['product.template'].search([('detailed_type','=','product')])
					for product in result:
						if product.qty_available < self.env.company.min_quantity:
							products_list.append([0,0,{'name':product.name,
												  'limit_quantity':self.env.company.min_quantity,
												  'stock_quantity':product.qty_available}])

			if self.env.company.notification_products == 'fore_product':
				if self.env.company.notification_product_type == 'variant':               
					result = self.env['product.product'].search([('detailed_type','=','product')])
	
					for product in result:
						if product.qty_available < product.min_quantity:
							name_att = ' '
							for attribute in product.product_template_attribute_value_ids:
							  name_att = name_att  +  attribute.name + '  '

							name_pro = ' '
							if product.product_template_attribute_value_ids :
							  name_pro = product.name + ' - ' +name_att + '  '
							else :
							  name_pro = product.name
							
							products_list.append([0,0,{'name':name_pro,
													  'limit_quantity':product.min_quantity,
												  'stock_quantity':product.qty_available,}])
				else:
					result = self.env['product.template'].search([('detailed_type','=','product')])

					for product in result:
						if product.qty_available < product.temp_min_quantity:
							products_list.append([0,0,{'name':product.name,
											  'limit_quantity':product.temp_min_quantity,
											  'stock_quantity':product.qty_available}])

			if self.env.company.notification_products == 'reorder':

				if self.env.company.notification_product_type == 'variant':                  
					result = self.env['product.product'].search([('detailed_type','=','product')])
					for product in result:
						if product.qty_available < product.qty_min:
							name_att = ' '
							for attribute in product.product_template_attribute_value_ids:
							  name_att = name_att  +  attribute.name + '  '

							name_pro = ' '
							if product.product_template_attribute_value_ids :
							  name_pro = product.name + ' - ' +name_att + '  '
							else :
							  name_pro = product.name
							vals = {'name':name_pro,
								  'limit_quantity':product.qty_min,
								  'stock_quantity':product.qty_available}

							products_list.append([0,0,vals])

				else:
					result = self.env['product.template'].search([('detailed_type','=','product')])
					for product in result:
						if product.qty_available < product.temp_qty_min:
						  products_list.append([0,0,{'name':product.name,
											  'limit_quantity':product.temp_qty_min,
											  'stock_quantity':product.qty_available}])

		if self.env.company.notification_base=='fore_cast':
			if self.env.company.notification_products=='for_all':

				if self.env.company.notification_product_type == 'variant':
					result = self.env['product.product'].search([('virtual_available','<',self.env.company.min_quantity),
															   ('detailed_type','=','product')])
					for product in result:
						name_att = ' '
						for attribute in product.product_template_attribute_value_ids:
						  name_att = name_att  +  attribute.name + '  '

						name_pro = ' '
						if product.product_template_attribute_value_ids :
						  name_pro = product.name + ' - ' +name_att + '  '

						else :
						  name_pro = product.name

						products_list.append([0,0,{'name':name_pro,
											  'limit_quantity':self.env.company.min_quantity,
											  'stock_quantity':product.virtual_available}])
				else:
					result = self.env['product.template'].search([])

					for product in result:
						if product.virtual_available < self.env.company.min_quantity:
						  products_list.append([0,0,{'name':product.name,
											  'limit_quantity':self.env.company.min_quantity,
											  'stock_quantity':product.virtual_available}])


			if self.env.company.notification_products == 'fore_product':
				
				if self.env.company.notification_product_type == 'variant':
					result = self.env['product.product'].search([('detailed_type','=','product')])

					for product in result:
						if product.virtual_available < product.min_quantity:
							name_att = ' '
							for attribute in product.product_template_attribute_value_ids:
							  name_att = name_att  +  attribute.name + '  '

							name_pro = ' '
							if product.product_template_attribute_value_ids :
							  name_pro = product.name + ' - ' +name_att + '  '
							else :
							  name_pro = product.name
							products_list.append([0,0,{'name':name_pro,
													  'limit_quantity':product.min_quantity,
												  'stock_quantity':product.virtual_available}])
				
				else:
					result = self.env['product.template'].search([('detailed_type','=','product')])

					for product in result:
						if product.virtual_available < product.temp_min_quantity:
							products_list.append([0,0,{'name':product.name,
											  'limit_quantity':product.temp_min_quantity,
											  'stock_quantity':product.virtual_available}])

			if self.env.company.notification_products == 'reorder':

				if self.env.company.notification_product_type == 'variant':                  
					result = self.env['product.product'].search([('detailed_type','=','product')])
					for product in result:
						if product.virtual_available < product.qty_min:
							name_att = ' '
							for attribute in product.product_template_attribute_value_ids:
							  name_att = name_att  +  attribute.name + '  '

							name_pro = ' '
							if product.product_template_attribute_value_ids :
							  name_pro = product.name + ' - ' +name_att + '  '
							else :
							  name_pro = product.name

							products_list.append([0,0,{'name':name_pro,
													  'limit_quantity':product.qty_min,
												  'stock_quantity':product.virtual_available}])
				else:
					result = self.env['product.template'].search([('detailed_type','=','product')])

					for product in result:
						if product.virtual_available < product.temp_qty_min:
							products_list.append([0,0,{'name':product.name,
											  'limit_quantity':product.temp_qty_min,
											  'stock_quantity':product.virtual_available}])
		
		self.env.company.low_stock_products_ids = products_list
		
		return 

	def action_low_stock_send(self):

		context = self._context
		current_uid = context.get('uid')
		su_id = self.env['res.users'].browse(current_uid)
		self.action_list_products_()
		company = self.env['res.company'].search([('notify_low_stock','=',True)])
		res = self.env['res.config.settings'].search([],order="id desc", limit=1)
		if su_id :
			current_user = su_id
		else:
			current_user = self.env.user
		# if res.id :
		if self.env.company.low_stock_products_ids:
			if company:
				for company_is in company:
					template_id = self.env['ir.model.data']._xmlid_lookup('bi_product_low_stock_notification.low_stock_email_template')[1]
					email_template_obj = self.env['mail.template'].browse(template_id)
					if template_id:
						values = email_template_obj._generate_template([res.id], ('subject', 'body_html', 'email_from', 'email_to', 'partner_to', 'email_cc', 'reply_to', 'scheduled_date'))[res.id]
						values['email_from'] = current_user.email
						values['email_to'] = company_is.email
						values['author_id'] = current_user.partner_id.id
						values['res_id'] = False
						# pdf = self.env.ref('bi_product_low_stock_notification.action_low_stock_report')._render([res.id])[0]
						pdf = self.env['ir.actions.report']._render_qweb_pdf("bi_product_low_stock_notification.action_low_stock_report", res.id)
						values['attachment_ids'] = [(0,0,{
							'name': 'Product Low Stock Report',
							'datas': base64.b64encode(pdf[0]),
							'res_model': self._name,
							'res_id': self.id,
							'mimetype': 'application/pdf',
							'type': 'binary',
							})]
						mail_mail_obj = self.env['mail.mail']
						msg_id = mail_mail_obj.create(values)
						if msg_id:
							msg_id.send()

			for partner in self.env['res.users'].search([]):
				if partner.notify_user:
					template_id = self.env['ir.model.data']._xmlid_lookup('bi_product_low_stock_notification.low_stock_email_template')[1]
					email_template_obj = self.env['mail.template'].browse(template_id)
					if template_id:
						values = email_template_obj._generate_template([res.id], ('subject', 'body_html', 'email_from', 'email_to', 'partner_to', 'email_cc', 'reply_to', 'scheduled_date'))[res.id]
						values['email_from'] = current_user.email
						values['email_to'] = partner.email
						values['author_id'] = current_user.partner_id.id
						values['res_id'] = False
						pdf = self.env['ir.actions.report']._render_qweb_pdf("bi_product_low_stock_notification.action_low_stock_report", res.id)
						values['attachment_ids'] = [(0,0,{
							'name': 'Product Low Stock Report',
							'datas': base64.b64encode(pdf[0]),
							'res_model': self._name,
							'res_id': self.id,
							'mimetype': 'application/pdf',
							'type': 'binary',
							})]
						mail_mail_obj = self.env['mail.mail']
						msg_id = mail_mail_obj.create(values)
						if msg_id:
							msg_id.send()

		return True


class LowstockLine(models.Model):
	_name='low.stock.line'
	_description="Low Stock Line"

	name=fields.Char(string='Product name')
	stock_quantity=fields.Float(string='Quantity')
	limit_quantity=fields.Float(string='Quantity limit')
	stock_product_id=fields.Many2one('low.stock.notification')
	new_product_id = fields.Many2one('product.product')
	company_id = fields.Many2one('res.company')