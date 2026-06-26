from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase

from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT


class TestFinancialRiskOverdue(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        cls.env.user.group_ids |= cls.env.ref(
            "account_financial_risk.group_account_financial_risk_manager"
        )
        cls.company = cls.env.company
        cls.company.invoice_unpaid_margin = 0
        cls.receivable_account = cls.env["account.account"].create(
            {
                "name": "Risk Overdue Receivable",
                "code": "S2C430RISK",
                "account_type": "asset_receivable",
                "reconcile": True,
            }
        )
        cls.income_account = cls.env["account.account"].create(
            {
                "name": "Risk Overdue Income",
                "code": "S2C700RISK",
                "account_type": "income_other",
            }
        )
        cls.sale_journal = cls.env["account.journal"].create(
            {
                "name": "Risk Overdue Sales Journal",
                "type": "sale",
                "code": "S2CRK",
                "company_id": cls.company.id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Overdue Risk Partner",
                "customer_rank": 1,
                "risk_account_overdue_invoices": True,
                "property_account_receivable_id": cls.receivable_account.id,
                "company_id": cls.company.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Overdue Risk Product",
                "list_price": 100.0,
                "invoice_policy": "order",
            }
        )
        cls.pricelist = cls.env["product.pricelist"].create(
            {"name": "Overdue Risk Pricelist"}
        )

    @classmethod
    def _create_sale_order(cls, partner=None):
        partner = partner or cls.partner
        return cls.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "pricelist_id": cls.pricelist.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": cls.product.name,
                            "product_id": cls.product.id,
                            "product_uom_qty": 1,
                            "product_uom_id": cls.product.uom_id.id,
                            "price_unit": 100.0,
                            "company_id": cls.company.id,
                        },
                    )
                ],
            }
        )

    @classmethod
    def _create_overdue_invoice(cls, partner=None):
        partner = partner or cls.partner
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": cls.sale_journal.id,
                "invoice_date": fields.Date.today() - timedelta(days=10),
                "invoice_date_due": fields.Date.today() - timedelta(days=5),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Overdue invoice line",
                            "account_id": cls.income_account.id,
                            "price_unit": 250.0,
                            "quantity": 1.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        invoice.line_ids.filtered(lambda line: line.debit).write(
            {"date_maturity": fields.Date.today() - timedelta(days=5)}
        )
        return invoice

    def test_compute_overdue_amount_and_open_pivot(self):
        self._create_overdue_invoice()

        self.assertAlmostEqual(self.partner.risk_amount_overdue_invoices, 250.0)

        action = self.partner.with_context(
            open_risk_field="risk_amount_overdue_invoices"
        ).open_risk_pivot_info()
        self.assertEqual(action["res_model"], "account.move.line")
        self.assertIn(("move_id.move_type", "=", "out_invoice"), action["domain"])

    def test_sale_order_is_blocked_by_overdue_invoice(self):
        self._create_overdue_invoice()
        sale_order = self._create_sale_order()

        wizard_action = sale_order.action_confirm()

        self.assertNotEqual(wizard_action, True)
        wizard = self.env[wizard_action["res_model"]].browse(wizard_action["res_id"])
        self.assertEqual(wizard.exception_msg, "This customer has overdue invoices.\n")

    def test_sale_order_confirms_without_overdue_invoice(self):
        partner = self.env["res.partner"].create(
            {
                "name": "No Overdue Risk Partner",
                "customer_rank": 1,
                "risk_account_overdue_invoices": True,
                "property_account_receivable_id": self.receivable_account.id,
                "company_id": self.company.id,
            }
        )
        sale_order = self._create_sale_order(partner=partner)

        result = sale_order.action_confirm()

        self.assertEqual(result, True)
        self.assertEqual(sale_order.state, "sale")