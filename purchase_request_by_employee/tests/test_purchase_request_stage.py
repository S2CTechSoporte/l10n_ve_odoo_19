from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPurchaseRequestStage(TransactionCase):

    def test_parent_stage_cycle_is_rejected(self):
        first_stage = self.env['purchase.request.stage'].create({'name': 'Stage A'})
        second_stage = self.env['purchase.request.stage'].create({
            'name': 'Stage B',
            'parent_id': first_stage.id,
        })

        with self.assertRaises(ValidationError):
            first_stage.parent_id = second_stage.id