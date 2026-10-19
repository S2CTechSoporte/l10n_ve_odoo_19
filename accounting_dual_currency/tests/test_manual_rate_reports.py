from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestManualRateReports(DualCurrencyTestCommon):
    """The reports show the reference amounts stored with the manual rate."""

    def _aged_total(self, report_xmlid, internal_type, currency):
        _, options = self._get_report_options(
            report_xmlid, self.rate_date_third, currency
        )
        handler = self.env["account.aged.partner.balance.report.handler"]
        return handler._aged_partner_report_custom_engine_common(
            options, internal_type, None, None
        )["total"]

    def test_aged_payable_uses_the_manual_rate_in_the_reference_currency(self):
        bill = self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        report = "account_reports.aged_payable_report"
        self.assertAlmostEqual(
            self._aged_total(report, "liability_payable", self.usd), 100.0, places=2
        )
        self.assertAlmostEqual(
            self._aged_total(report, "liability_payable", self.ves), 6000.0, places=2
        )

        self._create_payment(
            bill, self.ves, 3000.0, self.rate_date_second, manual_rate=60.0
        )
        self.assertAlmostEqual(
            self._aged_total(report, "liability_payable", self.usd), 50.0, places=2
        )
        self.assertAlmostEqual(
            self._aged_total(report, "liability_payable", self.ves), 3000.0, places=2
        )

    def test_aged_payable_of_a_usd_bill_uses_the_manual_rate(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        report = "account_reports.aged_payable_report"
        self.assertAlmostEqual(
            self._aged_total(report, "liability_payable", self.usd), 100.0, places=2
        )
        self.assertAlmostEqual(
            self._aged_total(report, "liability_payable", self.ves), 6000.0, places=2
        )
        self._create_payment(
            bill, self.usd, 40.0, self.rate_date_second, manual_rate=62.0
        )
        self.assertAlmostEqual(
            self._aged_total(report, "liability_payable", self.usd), 60.0, places=2
        )

    def test_aged_receivable_uses_the_manual_rate_in_the_reference_currency(self):
        self._create_invoice(
            self.ves, 6000.0, self.rate_date_invoice, "out_invoice", manual_rate=60.0
        )
        report = "account_reports.aged_receivable_report"
        self.assertAlmostEqual(
            self._aged_total(report, "asset_receivable", self.usd), 100.0, places=2
        )
        self.assertAlmostEqual(
            self._aged_total(report, "asset_receivable", self.ves), 6000.0, places=2
        )

    def test_partner_ledger_uses_the_manual_rate_in_the_reference_currency(self):
        bill = self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        report, company_options = self._get_report_options(
            "account_reports.partner_ledger_report", self.rate_date_third
        )
        _, secondary_options = self._get_report_options(
            "account_reports.partner_ledger_report", self.rate_date_third, self.usd
        )
        partner_id = report._get_generic_line_id("res.partner", bill.partner_id.id)
        company_options["unfolded_lines"] = [partner_id]
        secondary_options["unfolded_lines"] = [partner_id]

        for options, currency, expected_credit in (
            (company_options, self.ves, 6000.0),
            (secondary_options, self.usd, 100.0),
        ):
            with self.subTest(currency=currency.name):
                lines = report._get_lines(options)
                partner_line = next(
                    line for line in lines if line["name"] == bill.partner_id.name
                )
                columns = {
                    column["expression_label"]: column
                    for column in partner_line["columns"]
                    if column.get("expression_label")
                }
                self.assertAlmostEqual(
                    columns["credit"]["no_format"], expected_credit, places=2
                )
                self.assertAlmostEqual(
                    columns["balance"]["no_format"], -expected_credit, places=2
                )
                self.assertEqual(columns["balance"]["currency"], currency)

    def test_balance_sheet_uses_the_manual_rate_in_the_reference_currency(self):
        self._create_invoice(
            self.usd, 100.0, self.rate_date_invoice, "in_invoice", manual_rate=60.0
        )
        report = self.env.ref("account_reports.balance_sheet")
        for currency, expected_liabilities in ((self.ves, 6000.0), (self.usd, 100.0)):
            with self.subTest(currency=currency.name):
                _, options = self._get_report_options(
                    "account_reports.balance_sheet", self.rate_date_third, currency
                )
                lines = report.get_report_information(options)["lines"]
                liabilities = next(
                    line["columns"][0]["no_format"]
                    for line in lines
                    if line["name"] == "LIABILITIES"
                )
                self.assertAlmostEqual(liabilities, expected_liabilities, places=2)
