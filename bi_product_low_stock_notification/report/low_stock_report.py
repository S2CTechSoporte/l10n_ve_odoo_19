# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import models,fields,api

class low_stock_template(models.AbstractModel):
	_name = 'report.bi_product_low_stock_notification.low_stock_template'
	_description="Low Stock Template"

	@api.model
	def _get_report_values(self, docids, data=None):

		rec_ids = []
		for rec in self.env.company.low_stock_products_ids:
			rec_ids.append(rec)

		return {
				'doc_ids': docids,
				'data':data,
				'docs':self.env.company.id,
				'rec_ids':rec_ids,
			   }