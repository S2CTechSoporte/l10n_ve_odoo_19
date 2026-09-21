from odoo.tests import tagged

from .common import DualCurrencyTestCommon


@tagged("post_install", "-at_install")
class TestDualCurrencyAgedReports(DualCurrencyTestCommon):
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
