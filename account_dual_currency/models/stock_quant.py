from odoo import models, fields
from datetime import datetime
from odoo.exceptions import UserError

class StockQuant(models.Model):
    _inherit = "stock.quant"
    
    def action_apply_inventory(self):
        
        for rec in self:
            self = self.with_context({'inventory_date': rec.inventory_date})
       
        
        ret = super(StockQuant, self).action_apply_inventory()
       
        return ret
        

        
        
