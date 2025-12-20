from odoo import api, fields, models, _


class SequenceMixin(models.AbstractModel):
    _inherit = 'sequence.mixin'
     
    def _set_next_sequence(self):
        if 'journal_id' in self._fields and self.journal_id.custom_sequence_id:
            name = self.journal_id.custom_sequence_id._next()
            self[self._sequence_field] = name
            self._compute_split_sequence()
        else:
            return super()._set_next_sequence()    
    
    def _get_last_sequence(self, relaxed=False, with_prefix=None):
        if 'journal_id' in self._fields and self.journal_id.custom_sequence_id: 
            
            last = self.journal_id.custom_sequence_id.number_next_actual - 1
            name = self.journal_id.custom_sequence_id.get_next_char(last)
            return name
        else:
            return super()._get_last_sequence(relaxed, with_prefix)



