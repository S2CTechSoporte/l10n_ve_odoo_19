# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import api, fields, models, _


class PurchaseRequest(models.Model):
	_inherit = "purchase.request"

	approval_date = fields.Datetime(string="Approval date", readonly=True)

	@api.onchange('stage_id')
	def _compute_stage_id(self):
		if self.stage_id.final_stage and not self.stage_id.parent_id:
			self.approval_date = datetime.now()
		else:
			self.approval_date = False

	def button_approve(self):
		super(PurchaseRequest, self).button_approve()
		self._compute_stage_id()
