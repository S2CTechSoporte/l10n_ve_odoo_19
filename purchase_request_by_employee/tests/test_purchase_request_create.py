from odoo.tests.common import TransactionCase


class TestPurchaseRequestCreate(TransactionCase):

    def test_create_accepts_vals_list(self):
        records = self.env['purchase.request'].create([{}, {}])
        self.assertEqual(len(records), 2)
        self.assertTrue(all(records.mapped('name')))
