from odoo.addons.onboarding.controllers.onboarding import OnboardingController
from odoo import http
from odoo.http import request


class OnboardingController(OnboardingController):
    
    def get_onboarding_data(self, route_name=None, context=None):
        result = super(OnboardingController, self).get_onboarding_data(route_name, context)
       
        if not result:
            orders = request.env['sale.order'].sudo()._compute_orders_without_invoice()
            return {
                'html': request.env['ir.qweb']._render(
                    's2c_seniat_regulations.onboarding_alert', {'orders_without_invoice': orders})
            }
        return result