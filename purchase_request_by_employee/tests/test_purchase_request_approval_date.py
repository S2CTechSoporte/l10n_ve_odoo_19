from odoo.tests.common import TransactionCase


class TestPurchaseRequestApprovalDate(TransactionCase):

    def test_onchange_sets_and_resets_approval_date(self):
        stages = self.env['purchase.request.stage'].search([], order='sequence,id')
        final_stage = stages.filtered(lambda s: s.final_stage and not s.parent_id)[:1]
        non_final_stage = stages.filtered(lambda s: not (s.final_stage and not s.parent_id))[:1]

        self.assertTrue(final_stage)
        self.assertTrue(non_final_stage)

        request = self.env['purchase.request'].new({'stage_id': non_final_stage.id})
        request._onchange_approval_date()
        self.assertFalse(request.approval_date)

        request.stage_id = final_stage
        request._onchange_approval_date()
        self.assertTrue(request.approval_date)

    def test_button_approve_sets_approval_date_on_final_stage(self):
        final_stage = self.env['purchase.request.stage'].search([
            ('final_stage', '=', True),
            ('parent_id', '=', False),
        ], limit=1)
        self.assertTrue(final_stage)

        request = self.env['purchase.request'].create({'stage_id': final_stage.id})
        request.button_approve()
        self.assertTrue(request.approval_date)
