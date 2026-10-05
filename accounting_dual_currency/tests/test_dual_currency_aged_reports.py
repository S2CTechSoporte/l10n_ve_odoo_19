from odoo import Command
from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestDualCurrencyAgedReports(DualCurrencyTestCommon):
    def test_partner_ledger_and_balance_sheet_currency_options(self):
        for report_xmlid in (
            "account_reports.partner_ledger_report",
            "account_reports.balance_sheet",
            "account_reports.customer_statement_report",
        ):
            with self.subTest(report=report_xmlid):
                _, default_options = self._get_report_options(
                    report_xmlid, self.rate_date_third
                )
                self.assertEqual(default_options["dual_currency_id"], self.ves.id)
                _, options = self._get_report_options(
                    report_xmlid,
                    self.rate_date_third,
                    self.usd,
                )
                self.assertTrue(options["dual_currency_general_filter"])
                self.assertEqual(options["dual_currency_id"], self.usd.id)
                self.assertEqual(
                    {currency["currency_id"] for currency in options["dual_currencies"]},
                    {self.ves.id, self.usd.id},
                )

    def test_reports_hide_dual_currency_for_incompatible_companies(self):
        other_company = self.env.ref("base.main_company")
        for report_xmlid in (
            "account_reports.partner_ledger_report",
            "account_reports.balance_sheet",
            "account_reports.customer_statement_report",
        ):
            with self.subTest(report=report_xmlid):
                report = self.env.ref(report_xmlid).sudo().with_context(
                    allowed_company_ids=(self.company | other_company).ids
                )
                options = report.get_options(
                    {
                        "selected_variant_id": report.id,
                        "forced_companies": (self.company | other_company).ids,
                        "dual_currency_id": self.usd.id,
                    }
                )
                self.assertNotIn("dual_currency_id", options)
                self.assertNotIn("dual_currency_general_filter", options)

    def test_balance_sheet_uses_posted_secondary_balances(self):
        invoice = self._create_invoice(self.ves, 5000.0, self.rate_date_invoice)
        receivable = self._get_payment_term_line(invoice)
        bill = self._create_invoice(
            self.ves, 2600.0, self.rate_date_second, move_type="in_invoice"
        )
        payable = self._get_payment_term_line(bill)
        report, company_options = self._get_report_options(
            "account_reports.balance_sheet", self.rate_date_third
        )
        _, secondary_options = self._get_report_options(
            "account_reports.balance_sheet", self.rate_date_third, self.usd
        )
        assets_expression = report.line_ids.filtered(
            lambda line: line.name == "ASSETS"
        ).expression_ids.filtered(
            lambda expression: expression.label
            == company_options["columns"][0]["expression_label"]
        )
        self.assertEqual(len(assets_expression), 1)

        company_line = next(
            line for line in report._get_lines(company_options)
            if line["name"] == "Receivables"
        )
        secondary_line = next(
            line for line in report._get_lines(secondary_options)
            if line["name"] == "Receivables"
        )
        self.assertAlmostEqual(
            company_line["columns"][0]["no_format"], receivable.balance, places=2
        )
        self.assertAlmostEqual(
            secondary_line["columns"][0]["no_format"],
            receivable.balance_secondary_currency,
            places=2,
        )
        self.assertEqual(secondary_line["columns"][0]["currency"], self.usd)
        for options, currency, expected_assets, expected_liabilities in (
            (company_options, self.ves, receivable.balance, -payable.balance),
            (
                secondary_options,
                self.usd,
                receivable.balance_secondary_currency,
                -payable.balance_secondary_currency,
            ),
        ):
            with self.subTest(currency=currency.name):
                information = report.get_report_information(options)
                column_group_key = options["columns"][0]["column_group_key"]
                self.assertAlmostEqual(
                    information["column_groups_totals"][column_group_key][
                        assets_expression.id
                    ]["value"],
                    expected_assets,
                    places=2,
                )
                lines = information["lines"]
                totals = {
                    line["name"]: line["columns"][0]["no_format"]
                    for line in lines
                    if line["name"] in (
                        "ASSETS",
                        "Receivables",
                        "LIABILITIES",
                        "EQUITY (& EARNINGS)",
                    )
                }
                self.assertAlmostEqual(totals["ASSETS"], expected_assets, places=2)
                self.assertAlmostEqual(
                    totals["Receivables"], expected_assets, places=2
                )
                self.assertAlmostEqual(
                    totals["LIABILITIES"], expected_liabilities, places=2
                )
                self.assertAlmostEqual(
                    totals["EQUITY (& EARNINGS)"],
                    expected_assets - expected_liabilities,
                    places=2,
                )
        account_lines = report.get_expanded_lines(
            secondary_options,
            secondary_line["id"],
            secondary_line.get("groupby"),
            secondary_line["expand_function"],
            None,
            0,
            None,
        )
        account_line = next(
            line for line in account_lines
            if line["name"] == receivable.account_id.display_name
        )
        self.assertAlmostEqual(
            account_line["columns"][0]["no_format"],
            receivable.balance_secondary_currency,
            places=2,
        )
        self.assertEqual(account_line["columns"][0]["currency"], self.usd)

    def test_partner_ledger_uses_posted_secondary_amounts(self):
        invoice = self._create_invoice(self.ves, 5000.0, self.rate_date_invoice)
        receivable = self._get_payment_term_line(invoice)
        report, company_options = self._get_report_options(
            "account_reports.partner_ledger_report", self.rate_date_third
        )
        _, secondary_options = self._get_report_options(
            "account_reports.partner_ledger_report", self.rate_date_third, self.usd
        )
        partner_id = report._get_generic_line_id("res.partner", invoice.partner_id.id)
        company_options["unfolded_lines"] = [partner_id]
        secondary_options["unfolded_lines"] = [partner_id]

        for options, currency, expected_debit, expected_balance in (
            (company_options, self.ves, receivable.debit, receivable.balance),
            (
                secondary_options,
                self.usd,
                receivable.debit_secondary_currency,
                receivable.balance_secondary_currency,
            ),
        ):
            with self.subTest(currency=currency.name):
                lines = report._get_lines(options)
                partner_line = next(
                    line for line in lines if line["name"] == invoice.partner_id.name
                )
                move_line = next(
                    line for line in lines if line.get("parent_id") == partner_line["id"]
                    and line["name"] != "Initial Balance"
                )
                for line in (partner_line, move_line):
                    columns = {
                        column["expression_label"]: column
                        for column in line["columns"]
                        if column.get("expression_label")
                    }
                    self.assertAlmostEqual(
                        columns["debit"]["no_format"], expected_debit, places=2
                    )
                    self.assertAlmostEqual(
                        columns["balance"]["no_format"], expected_balance, places=2
                    )
                    self.assertEqual(columns["balance"]["currency"], currency)

    def test_customer_statement_defaults_and_allows_currency_switching(self):
        report = self.env.ref("account_reports.customer_statement_report")
        action = self.partner_customer.open_customer_statement()
        self.assertNotIn("dual_currency_id", action["params"]["options"])
        options = report.get_options(
            {"selected_variant_id": report.id, **action["params"]["options"]}
        )
        self.assertEqual(options["dual_currency_id"], self.ves.id)
        self.assertTrue(options["dual_currency_general_filter"])

        selected_options = report.get_options({**options, "dual_currency_id": self.usd.id})
        self.assertEqual(selected_options["dual_currency_id"], self.usd.id)
        self.assertEqual(
            {currency["currency_id"] for currency in selected_options["dual_currencies"]},
            {self.ves.id, self.usd.id},
        )
        self.assertEqual(
            [currency["currency_id"] for currency in selected_options["dual_currencies"]
             if currency["currency_selected"]],
            [self.usd.id],
        )

    def test_customer_statement_inherits_aged_currency_and_balances(self):
        statement = self.env.ref("account_reports.customer_statement_report")
        handler = self.env["account.aged.partner.balance.report.handler"]
        for move_type, source_xmlid in (
            ("out_invoice", "account_reports.aged_receivable_report"),
            ("in_invoice", "account_reports.aged_payable_report"),
        ):
            invoice = self._create_invoice(
                self.ves, 5000.0, self.rate_date_invoice, move_type=move_type
            )
            payment_term = self._get_payment_term_line(invoice)
            for currency, balance in (
                (self.ves, payment_term.balance),
                (self.usd, payment_term.balance_secondary_currency),
            ):
                with self.subTest(source=source_xmlid, currency=currency.name):
                    source, source_options = self._get_report_options(
                        source_xmlid, self.rate_date_third, currency
                    )
                    action = handler.open_customer_statement(
                        source_options,
                        {
                            "line_id": source._get_generic_line_id(
                                "res.partner", invoice.partner_id.id
                            )
                        },
                    )
                    self.assertEqual(
                        action["params"]["options"]["dual_currency_id"], currency.id
                    )
                    self.assertIn(
                        invoice.partner_id.id, action["params"]["options"]["partner_ids"]
                    )
                    options = statement.get_options(
                        {
                            "selected_variant_id": statement.id,
                            **action["params"]["options"],
                            "date": {
                                "date_from": self.rate_date_invoice,
                                "date_to": self.rate_date_third,
                                "mode": "range",
                                "filter": "custom",
                            },
                        }
                    )
                    self.assertEqual(options["dual_currency_id"], currency.id)
                    partner_id = statement._get_generic_line_id(
                        "res.partner", invoice.partner_id.id
                    )
                    options["unfolded_lines"] = [partner_id]
                    lines = statement._get_lines(options)
                    partner_line = next(line for line in lines if line["id"] == partner_id)
                    move_line = next(
                        line for line in lines
                        if line.get("parent_id") == partner_line["id"]
                        and line["name"] != "Initial Balance"
                    )
                    for line in (partner_line, move_line):
                        columns = {
                            column["expression_label"]: column
                            for column in line["columns"]
                            if column.get("expression_label")
                        }
                        for label in ("amount", "balance"):
                            self.assertAlmostEqual(
                                columns[label]["no_format"], balance, places=2
                            )
                            self.assertEqual(columns[label]["currency"], currency)

    def test_partner_ledger_initial_balance_and_indirect_reconciliation(self):
        invoice = self._create_invoice(self.ves, 5000.0, self.rate_date_invoice)
        receivable = self._get_payment_term_line(invoice)
        clearing_move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": self.rate_date_second,
                "journal_id": self.misc_journal.id,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Unassigned receipt",
                            "account_id": receivable.account_id.id,
                            "credit": 2000.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Receipt counterpart",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 2000.0,
                        }
                    ),
                ],
            }
        )
        clearing_move.action_post()
        receipt = clearing_move.line_ids.filtered(
            lambda line: line.account_id == receivable.account_id
        )
        self.assertFalse(receipt.partner_id)
        (receivable | receipt).reconcile()
        partial = receivable.matched_credit_ids.filtered(
            lambda match: match.credit_move_id == receipt
        )

        report = self.env.ref("account_reports.partner_ledger_report")
        options = report.get_options(
            {
                "selected_variant_id": report.id,
                "dual_currency_id": self.usd.id,
                "date": {
                    "date_from": self.rate_date_second,
                    "date_to": self.rate_date_third,
                    "mode": "range",
                    "filter": "custom",
                },
            }
        )
        partner_id = report._get_generic_line_id("res.partner", invoice.partner_id.id)
        options["unfolded_lines"] = [partner_id]
        lines = report._get_lines(options)
        partner_line = next(
            line for line in lines if line["name"] == invoice.partner_id.name
        )
        initial_line = next(
            line for line in lines if line.get("parent_id") == partner_id
            and line["name"] == "Initial Balance"
        )
        receipt_line = next(
            line for line in lines if line.get("parent_id") == partner_id
            and "Unassigned receipt" in line["name"]
        )
        expected_balance = (
            receivable.balance_secondary_currency - partial.amount_secondary_currency
        )
        self.assertAlmostEqual(
            initial_line["columns"][-1]["no_format"],
            receivable.balance_secondary_currency,
            places=2,
        )
        self.assertAlmostEqual(
            receipt_line["columns"][-1]["no_format"], expected_balance, places=2
        )
        self.assertAlmostEqual(
            partner_line["columns"][-1]["no_format"], expected_balance, places=2
        )
        expanded_lines = report.get_expanded_lines(
            options,
            partner_line["id"],
            partner_line.get("groupby"),
            partner_line["expand_function"],
            None,
            0,
            None,
        )
        expanded_receipt = next(
            line for line in expanded_lines if "Unassigned receipt" in line["name"]
        )
        self.assertAlmostEqual(
            expanded_receipt["columns"][-1]["no_format"], expected_balance, places=2
        )

    def test_report_uses_selected_company_currency_not_active_company(self):
        invoice = self._create_invoice(self.ves, 5000.0, self.rate_date_invoice)
        receivable = self._get_payment_term_line(invoice)
        other_company = self.env.ref("base.main_company")
        self.assertNotEqual(other_company, self.company)
        self.assertNotEqual(other_company.secondary_currency_id, self.usd)

        for report_xmlid, line_name in (
            ("account_reports.partner_ledger_report", invoice.partner_id.name),
            ("account_reports.balance_sheet", "Receivables"),
        ):
            with self.subTest(report=report_xmlid):
                report, options = self._get_report_options(
                    report_xmlid, self.rate_date_third, self.usd
                )
                lines = report.sudo().with_context(
                    allowed_company_ids=(self.company | other_company).ids
                ).with_company(other_company)._get_lines(options)
                report_line = next(
                    line for line in lines if line["name"] == line_name
                )
                self.assertAlmostEqual(
                    report_line["columns"][-1]["no_format"],
                    receivable.balance_secondary_currency,
                    places=2,
                )

    def test_aged_receivable_defaults_to_ves(self):
        invoice = self._create_invoice(
            self.ves,
            5000.0,
            self.rate_date_invoice,
        )
        report, options = self._get_report_options(
            "account_reports.aged_receivable_report",
            self.rate_date_third,
        )
        self.assertEqual(options["dual_currency_id"], self.ves.id)
        self.assertEqual(
            {currency["currency_id"] for currency in options["dual_currencies"]},
            {self.ves.id, self.usd.id},
        )

        totals = self.env[
            "account.aged.partner.balance.report.handler"
        ]._aged_partner_report_custom_engine_common(
            options,
            "asset_receivable",
            None,
            None,
        )
        self.assertAlmostEqual(totals["total"], 5000.0, places=2)
        self.assertEqual(invoice.currency_id, self.ves)
        self.assertEqual(report, self.env.ref("account_reports.aged_receivable_report"))

    def test_aged_receivable_usd_respects_report_cutoff(self):
        invoice = self._create_invoice(
            self.usd,
            1000.0,
            self.rate_date_invoice,
        )
        self._create_payment(
            invoice,
            self.usd,
            200.0,
            self.rate_date_invoice,
        )
        self._create_payment(
            invoice,
            self.ves,
            15600.0,
            self.rate_date_second,
        )
        handler = self.env["account.aged.partner.balance.report.handler"]

        _, cutoff_options = self._get_report_options(
            "account_reports.aged_receivable_report",
            self.rate_date_invoice,
            self.usd,
        )
        cutoff_totals = handler._aged_partner_report_custom_engine_common(
            cutoff_options,
            "asset_receivable",
            None,
            None,
        )
        cutoff_partner_totals = dict(
            handler._aged_partner_report_custom_engine_common(
                cutoff_options,
                "asset_receivable",
                "partner_id",
                "id",
            )
        )
        self.assertAlmostEqual(cutoff_totals["total"], 800.0, delta=0.02)
        self.assertAlmostEqual(
            cutoff_partner_totals[invoice.partner_id.id]["total"],
            800.0,
            delta=0.02,
        )

        _, final_options = self._get_report_options(
            "account_reports.aged_receivable_report",
            self.rate_date_third,
            self.usd,
        )
        final_totals = handler._aged_partner_report_custom_engine_common(
            final_options,
            "asset_receivable",
            None,
            None,
        )
        self.assertAlmostEqual(final_totals["total"], 500.0, delta=0.02)
        self.assertAlmostEqual(
            sum(final_totals[f"period{index}"] for index in range(6)),
            final_totals["total"],
            delta=0.02,
        )

    def test_aged_receivable_selected_reference_currency(self):
        invoice = self._create_invoice(
            self.ves,
            5000.0,
            self.rate_date_invoice,
        )
        self._create_payment(
            invoice,
            self.ves,
            2000.0,
            self.rate_date_second,
        )
        report, options = self._get_report_options(
            "account_reports.aged_receivable_report",
            self.rate_date_third,
            self.usd,
        )
        handler = self.env["account.aged.partner.balance.report.handler"]
        totals = handler._aged_partner_report_custom_engine_common(
            options,
            "asset_receivable",
            None,
            None,
        )
        partner_totals = dict(
            handler._aged_partner_report_custom_engine_common(
                options,
                "asset_receivable",
                "partner_id",
                "id",
            )
        )
        expected = self.usd.round(100.0 - (2000.0 / 52.0))
        self.assertAlmostEqual(totals["total"], expected, delta=0.02)
        self.assertAlmostEqual(
            partner_totals[invoice.partner_id.id]["total"],
            expected,
            delta=0.02,
        )
        self.assertAlmostEqual(
            sum(totals[f"period{index}"] for index in range(6)),
            totals["total"],
            delta=0.02,
        )

        column_group_key = next(iter(options["column_groups"]))
        column = report._build_column_dict(
            totals["total"],
            {
                "column_group_key": column_group_key,
                "expression_label": "total",
                "figure_type": "monetary",
            },
            options=options,
        )
        self.assertEqual(column["currency"], self.usd)
        self.assertEqual(column["format_params"]["currency_id"], self.usd.id)

    def test_aged_payable_selected_reference_currency(self):
        bill = self._create_invoice(
            self.ves,
            5000.0,
            self.rate_date_invoice,
            move_type="in_invoice",
        )
        self._create_payment(
            bill,
            self.ves,
            2000.0,
            self.rate_date_second,
        )
        _, options = self._get_report_options(
            "account_reports.aged_payable_report",
            self.rate_date_third,
            self.usd,
        )
        handler = self.env["account.aged.partner.balance.report.handler"]
        totals = handler._aged_partner_report_custom_engine_common(
            options,
            "liability_payable",
            None,
            None,
        )
        partner_totals = dict(
            handler._aged_partner_report_custom_engine_common(
                options,
                "liability_payable",
                "partner_id",
                "id",
            )
        )
        expected = self.usd.round(100.0 - (2000.0 / 52.0))
        self.assertAlmostEqual(totals["total"], expected, delta=0.02)
        self.assertAlmostEqual(
            partner_totals[bill.partner_id.id]["total"],
            expected,
            delta=0.02,
        )
        self.assertAlmostEqual(
            sum(totals[f"period{index}"] for index in range(6)),
            totals["total"],
            delta=0.02,
        )
