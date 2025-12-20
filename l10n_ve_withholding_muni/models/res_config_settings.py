# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    muni_wh_agent = fields.Boolean(string='Retention agent', help='True if your partner is a municipal retention agent', 
        related="company_id.muni_wh_agent",readonly=False)
    purchase_jrl_id = fields.Many2one('account.journal', string='Purchase journal',
        related="company_id.purchase_jrl_id",readonly=False)
    sale_jrl_id = fields.Many2one('account.journal', string='Sales journal',
        related="company_id.sale_jrl_id",readonly=False)
    account_ret_muni_receivable_id = fields.Many2one('account.account', string='Cuenta Retencion Clientes',
        related="company_id.account_ret_muni_receivable_id",readonly=False)
    account_ret_muni_payable_id = fields.Many2one('account.account', string='Cuenta Retencion Proveedores',
        related="company_id.account_ret_muni_payable_id",readonly=False)
    nit = fields.Char(string='NIT', help='Old tax identification number replaced by the current RIF',
        related="company_id.nit",readonly=False)
    econ_act_license = fields.Char(string='License number', help='Economic activity license number',
        related="company_id.econ_act_license",readonly=False)
    nifg = fields.Char(string='NIFG', help='Number assigned by Satrin',
        related="company_id.nifg",readonly=False)