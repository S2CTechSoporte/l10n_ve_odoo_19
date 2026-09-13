from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSalespersonState(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.state = cls.env["res.country.state"].create(
            {
                "name": "Test Zone",
                "code": "TZ",
                "country_id": cls.env.ref("base.us").id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Customer Zone",
                "state_id": cls.state.id,
                "country_id": cls.state.country_id.id,
                "user_id": cls.env.user.id,
            }
        )
        cls.receivable_account = cls.partner.property_account_receivable_id
        cls.counterpart_account = cls.env["account.account"].search(
            [
                ("account_type", "in", ("income", "income_other")),
                ("company_ids", "in", cls.env.company.id),
            ],
            limit=1,
        )
        cls.journal = cls.env["account.journal"].search(
            [
                ("type", "=", "sale"),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )

        if not cls.receivable_account:
            raise AssertionError("A receivable account is required for the report tests")
        if not cls.counterpart_account:
            raise AssertionError("An income account is required for the report tests")
        if not cls.journal:
            raise AssertionError("A sales journal is required for the report tests")

    def _create_receivable_entry(self, partner, salesperson):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.today(),
                "journal_id": self.journal.id,
                "invoice_user_id": salesperson.id if salesperson else False,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Salesperson and zone filter test",
                            "partner_id": partner.id,
                            "account_id": self.receivable_account.id,
                            "date_maturity": fields.Date.today(),
                            "debit": 100.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Salesperson and zone filter counterpart",
                            "account_id": self.counterpart_account.id,
                            "credit": 100.0,
                        }
                    ),
                ],
            }
        )
        move.invoice_user_id = salesperson
        move.action_post()
        return move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )

    def test_related_zone_fields_are_stored_and_searchable(self):
        sale_order = self.env["sale.order"].create(
            {"partner_id": self.partner.id}
        )
        account_move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
            }
        )

        self.assertEqual(sale_order.state_id, self.state)
        self.assertEqual(account_move.state_id, self.state)
        self.assertTrue(self.env["sale.order"]._fields["state_id"].store)
        self.assertTrue(self.env["account.move"]._fields["state_id"].store)
        self.assertIn(
            sale_order,
            self.env["sale.order"].search([("state_id", "=", self.state.id)]),
        )
        self.assertIn(
            account_move,
            self.env["account.move"].search([("state_id", "=", self.state.id)]),
        )

    def test_zone_label_is_translated_to_spanish(self):
        field_description = self.env["sale.order"].with_context(lang="es_VE").fields_get(
            ["state_id"]
        )
        salesperson_column = self.env.ref(
            "s2c_salesperson_state.aged_receivable_report_salesperson"
        ).with_context(lang="es_VE")
        state_column = self.env.ref(
            "s2c_salesperson_state.aged_receivable_report_state"
        ).with_context(lang="es_VE")

        self.assertEqual(field_description["state_id"]["string"], "Zona")
        self.assertEqual(salesperson_column.name, "Vendedor")
        self.assertEqual(state_column.name, "Zona")

    def test_aged_receivable_restores_filters_and_applies_domain(self):
        report = self.env.ref("account_reports.aged_receivable_report")
        options = report.get_options(
            {
                "salesperson_ids": [self.env.user.id],
                "state_ids": [self.state.id],
            }
        )

        self.assertTrue(report.filter_salesperson)
        self.assertTrue(report.filter_state)
        self.assertEqual(options["salesperson_ids"], [self.env.user.id])
        self.assertEqual(options["state_ids"], [self.state.id])
        self.assertIn(
            ("move_id.invoice_user_id", "in", [self.env.user.id]),
            options["forced_domain"],
        )
        self.assertIn(
            ("partner_id.state_id", "in", [self.state.id]),
            options["forced_domain"],
        )
        self.assertEqual(
            options["custom_display_config"]["components"]["AccountReportFilters"],
            "S2CSalespersonStateAgedPartnerBalanceFilters",
        )

    def test_aged_receivable_columns_follow_total_and_can_be_reordered(self):
        report = self.env.ref("account_reports.aged_receivable_report")
        salesperson_column = self.env.ref(
            "s2c_salesperson_state.aged_receivable_report_salesperson"
        )
        state_column = self.env.ref(
            "s2c_salesperson_state.aged_receivable_report_state"
        )
        salesperson_expression = self.env.ref(
            "s2c_salesperson_state.aged_receivable_line_salesperson"
        )
        state_expression = self.env.ref(
            "s2c_salesperson_state.aged_receivable_line_state"
        )

        options = report.get_options({})
        labels = [column["expression_label"] for column in options["columns"]]

        self.assertLess(labels.index("total"), labels.index("salesperson"))
        self.assertLess(labels.index("salesperson"), labels.index("state"))
        self.assertEqual(salesperson_column.report_id, report)
        self.assertEqual(state_column.report_id, report)
        self.assertEqual(salesperson_column.figure_type, "string")
        self.assertEqual(state_column.figure_type, "string")
        self.assertEqual(salesperson_expression.label, "salesperson")
        self.assertEqual(salesperson_expression.subformula, "salesperson")
        self.assertFalse(salesperson_expression.auditable)
        self.assertEqual(state_expression.label, "state")
        self.assertEqual(state_expression.subformula, "state")
        self.assertFalse(state_expression.auditable)

        state_column.sequence = salesperson_column.sequence - 1
        report.invalidate_recordset(["column_ids"])
        reordered_options = report.get_options({})
        reordered_labels = [
            column["expression_label"] for column in reordered_options["columns"]
        ]
        self.assertLess(
            reordered_labels.index("state"),
            reordered_labels.index("salesperson"),
        )

    def test_aged_receivable_columns_show_detail_values_with_unfold_all(self):
        move_line = self._create_receivable_entry(self.partner, self.env.user)
        report = self.env.ref("account_reports.aged_receivable_report")
        options = report.get_options({"unfold_all": True})

        report_lines = report._get_lines(options)
        detail_line = next(
            line
            for line in report_lines
            if report._get_res_id_from_line_id(line["id"], "account.move.line")
            == move_line.id
        )
        detail_columns = {
            column["expression_label"]: column for column in detail_line["columns"]
        }

        self.assertEqual(
            detail_columns["salesperson"]["no_format"],
            self.env.user.display_name,
        )
        self.assertEqual(
            detail_columns["state"]["no_format"],
            self.state.display_name,
        )

        partner_line = next(
            line
            for line in report_lines
            if report._get_res_id_from_line_id(line["id"], "res.partner")
            == self.partner.id
        )
        partner_columns = {
            column["expression_label"]: column for column in partner_line["columns"]
        }
        self.assertIsNone(partner_columns["salesperson"]["no_format"])
        self.assertIsNone(partner_columns["state"]["no_format"])

    def test_aged_receivable_filter_domain_selects_matching_move_lines(self):
        matching_line = self._create_receivable_entry(self.partner, self.env.user)
        other_partner = self.env["res.partner"].create(
            {
                "name": "Test Customer Other Salesperson",
                "state_id": self.state.id,
                "country_id": self.state.country_id.id,
                "user_id": False,
            }
        )
        other_line = self._create_receivable_entry(other_partner, self.env["res.users"])

        report = self.env.ref("account_reports.aged_receivable_report")
        options = report.get_options(
            {
                "salesperson_ids": [self.env.user.id],
                "state_ids": [self.state.id],
            }
        )
        matching_move_lines = self.env["account.move.line"].search(
            report._get_options_domain(options, "strict_range")
        )

        self.assertIn(matching_line, matching_move_lines)
        self.assertNotIn(other_line, matching_move_lines)

    def test_aged_payable_does_not_enable_receivable_filters(self):
        report = self.env.ref("account_reports.aged_payable_report")
        options = report.get_options({})

        self.assertNotIn("salesperson_ids", options)
        self.assertNotIn("state_ids", options)

    def test_delivery_date_columns_are_preserved_when_installed(self):
        delivery_module = self.env["ir.module.module"].search(
            [("name", "=", "s2c_delivery_date"), ("state", "=", "installed")],
            limit=1,
        )
        if not delivery_module:
            self.skipTest("s2c_delivery_date is not installed")

        report = self.env.ref("account_reports.aged_receivable_report")
        options = report.get_options({})
        expression_labels = {
            column["expression_label"] for column in options["columns"]
        }

        self.assertTrue(
            {
                "delivery_date",
                "delivery_time",
                "invoice_date_due",
                "remaining_days",
            }.issubset(expression_labels)
        )