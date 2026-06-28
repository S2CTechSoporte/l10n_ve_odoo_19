# Copyright 2018 ForgeFlow S.L.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import common, tagged

from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT
from odoo.addons.base_tier_validation.tests.common import CommonTierValidation


class TestPurchaseTierValidation(CommonTierValidation):
    def test_01_tier_definition_models(self):
        res = self.tier_def_obj._get_tier_validation_model_names()
        self.assertIn("purchase.order", res)


@tagged("post_install", "-at_install")
class TestPurchaseTierValidationFlow(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        cls.po_model = cls.env.ref("purchase.model_purchase_order")
        cls.env.company.po_double_validation = "one_step"

        reviewer_group_ids = (
            cls.env.ref("base.group_system")
            + cls.env.ref("purchase.group_purchase_manager")
        ).ids
        cls.reviewer_user = cls.env["res.users"].create(
            {
                "name": "Purchase Reviewer",
                "login": "purchase_reviewer",
                "group_ids": [(6, 0, reviewer_group_ids)],
                "email": "purchase-reviewer@example.com",
            }
        )
        requester_group_ids = cls.env.ref("purchase.group_purchase_user").ids
        cls.requester_user = cls.env["res.users"].create(
            {
                "name": "Purchase Requester",
                "login": "purchase_requester",
                "group_ids": [(6, 0, requester_group_ids)],
                "email": "purchase-requester@example.com",
            }
        )

        cls.env["tier.definition"].create(
            {
                "model_id": cls.po_model.id,
                "review_type": "individual",
                "reviewer_id": cls.reviewer_user.id,
                "definition_domain": "[('amount_untaxed', '>', 50.0)]",
            }
        )
        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Vendor for test",
                "supplier_rank": 1,
                "company_type": "company",
                "people_type_company": "pjnd",
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Purchase Product for test", "standard_price": 120.0}
        )

    def test_validation_purchase_order(self):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": "Test line",
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "product_uom_id": self.product.uom_po_id.id,
                            "price_unit": 120.0,
                            "date_planned": fields.Datetime.now(),
                        },
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError):
            po.with_user(self.requester_user).button_confirm()
        po.with_user(self.requester_user).request_validation()
        po.with_user(self.reviewer_user).validate_tier()
        po.with_user(self.requester_user).button_confirm()
        self.assertIn(po.state, ("purchase", "approved"))
