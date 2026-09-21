from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class DualCurrencyTestCommon(AccountTestInvoicingCommon):
    country_code = "VE"
    chart_template = "ve"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.ves.active = True
        cls.usd.active = True
        cls.company.write(
            {
                "country_id": cls.env.ref("base.ve").id,
                "currency_id": cls.ves.id,
                "fcurrency_id": cls.usd.id,
            }
        )
        cls.company_data["currency"] = cls.ves

        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.purchase_journal = cls.company_data["default_journal_purchase"]
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.misc_journal = cls.company_data["default_journal_misc"]

        cls.partner_customer = cls.env["res.partner"].create(
            {
                "name": "Venezuela Dual Currency Customer",
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.partner_vendor = cls.env["res.partner"].create(
            {
                "name": "Venezuela Dual Currency Vendor",
                "country_id": cls.env.ref("base.ve").id,
                "supplier_rank": 1,
            }
        )
        cls.product = cls._create_product(
            name="Venezuela Dual Currency Service",
            list_price=100.0,
            taxes_id=[Command.clear()],
        )

        cls.rate_date_invoice = fields.Date.to_date("2026-01-10")
        cls.rate_date_second = fields.Date.to_date("2026-01-20")
        cls.rate_date_third = fields.Date.to_date("2026-01-30")
        cls._set_rate(cls.usd, cls.company, cls.rate_date_invoice, 50.0)
        cls._set_rate(cls.usd, cls.company, cls.rate_date_second, 52.0)
        cls._set_rate(cls.usd, cls.company, cls.rate_date_third, 54.0)

    @classmethod
    def _set_rate(cls, currency, company, rate_date, inverse_rate):
        values = {
            "company_id": company.id,
            "currency_id": currency.id,
            "name": rate_date,
            "rate": 1.0 / inverse_rate,
        }
        rate = cls.env["res.currency.rate"].search(
            [
                ("company_id", "=", company.id),
                ("currency_id", "=", currency.id),
                ("name", "=", rate_date),
            ],
            limit=1,
        )
        if rate:
            rate.write(values)
        else:
            cls.env["res.currency.rate"].create(values)

    def _convert(self, amount, from_currency, to_currency, rate_date):
        return from_currency.with_context(manual_rate=False)._convert(
            amount,
            to_currency,
            self.company,
            rate_date,
            False,
        )

    def _create_invoice(
        self,
        currency,
        amount,
        invoice_date,
        move_type="out_invoice",
    ):
        partner = (
            self.partner_customer
            if move_type.startswith("out_")
            else self.partner_vendor
        )
        journal = (
            self.sale_journal
            if move_type.startswith("out_")
            else self.purchase_journal
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "invoice_date": invoice_date,
                "date": invoice_date,
                "partner_id": partner.id,
                "journal_id": journal.id,
                "currency_id": currency.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "quantity": 1.0,
                            "price_unit": amount,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _create_payment(self, invoice, currency, amount, payment_date):
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create(
            {
                "payment_date": payment_date,
                "journal_id": self.bank_journal.id,
                "amount": amount,
                "currency_id": currency.id,
            }
        )
        payment = wizard._create_payments()
        if payment.state == "in_process":
            payment.action_validate()
        return payment

    def _get_payment_term_line(self, move):
        return move.line_ids.filtered(
            lambda line: line.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )[:1]

    def _round(self, currency, amount):
        return currency.round(amount)

    def _assert_invoice_dual_totals(
        self,
        invoice,
        expected_document,
        expected_local,
        expected_reference,
    ):
        invoice.invalidate_recordset(
            [
                "amount_total",
                "amount_total_local_currency",
                "amount_total_fcurrency",
                "fcurrency_id",
            ]
        )
        self.assertEqual(invoice.fcurrency_id, self.usd)
        self.assertAlmostEqual(
            invoice.amount_total,
            self._round(invoice.currency_id, expected_document),
            delta=invoice.currency_id.rounding,
        )
        self.assertAlmostEqual(
            invoice.amount_total_local_currency,
            self._round(self.ves, expected_local),
            delta=self.ves.rounding,
        )
        self.assertAlmostEqual(
            invoice.amount_total_fcurrency,
            self._round(self.usd, expected_reference),
            delta=self.usd.rounding,
        )

    def _assert_invoice_residuals(
        self,
        invoice,
        expected_document,
        expected_local,
        expected_reference,
    ):
        invoice.invalidate_recordset(
            [
                "amount_residual",
                "amount_residual_local_currency",
                "amount_residual_fcurrency",
            ]
        )
        self.assertAlmostEqual(
            invoice.amount_residual,
            self._round(invoice.currency_id, expected_document),
            delta=invoice.currency_id.rounding * 2,
        )
        self.assertAlmostEqual(
            invoice.amount_residual_local_currency,
            self._round(self.ves, expected_local),
            delta=self.ves.rounding * 2,
        )
        self.assertAlmostEqual(
            invoice.amount_residual_fcurrency,
            self._round(self.usd, expected_reference),
            delta=self.usd.rounding * 2,
        )

    def _assert_move_line_dual_fields(self, move):
        for line in move.line_ids.filtered(
            lambda candidate: candidate.display_type
            not in ("line_section", "line_subsection", "line_note")
        ):
            line.invalidate_recordset(
                [
                    "debit_fcurrency",
                    "credit_fcurrency",
                    "balance_fcurrency",
                    "amount_residual_fcurrency",
                ]
            )
            self.assertEqual(line.fcurrency_id, self.usd)
            self.assertAlmostEqual(
                line.debit_fcurrency - line.credit_fcurrency,
                line.balance_fcurrency,
                delta=self.usd.rounding,
            )

        product_line = move.invoice_line_ids[:1]
        if product_line:
            self.assertAlmostEqual(
                product_line.price_subtotal_fcurrency,
                move.currency_id._convert(
                    product_line.price_subtotal,
                    self.usd,
                    self.company,
                    move._get_dual_currency_reference_rate_date(),
                    False,
                ),
                delta=self.usd.rounding,
            )

    def _assert_partial_reference_amounts(self, invoice):
        term_line = self._get_payment_term_line(invoice)
        partials = term_line.matched_debit_ids | term_line.matched_credit_ids
        for partial in partials:
            partial.invalidate_recordset(["amount_fcurrency"])
            if partial.debit_currency_id == self.usd:
                expected = partial.debit_amount_currency
            elif partial.credit_currency_id == self.usd:
                expected = partial.credit_amount_currency
            else:
                expected = self._convert(
                    partial.amount,
                    self.ves,
                    self.usd,
                    partial.max_date,
                )
            self.assertAlmostEqual(
                partial.amount_fcurrency,
                expected,
                delta=self.usd.rounding,
            )

    def _assert_payment_widgets(
        self,
        invoice,
        expected_reference_amounts,
        expected_local_amounts,
    ):
        invoice.invalidate_recordset(
            [
                "invoice_payments_widget",
                "invoice_payments_widget_fcurrency",
                "invoice_payments_widget_local_currency",
            ]
        )
        reference_widget = invoice.invoice_payments_widget_fcurrency or {
            "content": []
        }
        local_widget = invoice.invoice_payments_widget_local_currency or {
            "content": []
        }
        reference_lines = [
            line
            for line in reference_widget.get("content", [])
            if not line.get("is_exchange")
        ]
        local_lines = [
            line
            for line in local_widget.get("content", [])
            if not line.get("is_exchange")
        ]
        self.assertEqual(len(reference_lines), len(expected_reference_amounts))
        self.assertEqual(len(local_lines), len(expected_local_amounts))
        self.assertEqual(
            {line["currency_id"] for line in reference_lines},
            {self.usd.id},
        )
        self.assertEqual(
            {line["currency_id"] for line in local_lines},
            {self.ves.id},
        )
        self.assertEqual(
            sorted(self.usd.round(line["amount"]) for line in reference_lines),
            sorted(self.usd.round(amount) for amount in expected_reference_amounts),
        )
        self.assertEqual(
            sorted(self.ves.round(line["amount"]) for line in local_lines),
            sorted(self.ves.round(amount) for amount in expected_local_amounts),
        )

    def _run_invoice_payment_scenario(
        self,
        invoice_currency,
        invoice_amount,
        payments,
    ):
        invoice = self._create_invoice(
            invoice_currency,
            invoice_amount,
            self.rate_date_invoice,
        )
        expected_total_local = self._convert(
            invoice_amount,
            invoice_currency,
            self.ves,
            self.rate_date_invoice,
        )
        expected_total_reference = self._convert(
            invoice_amount,
            invoice_currency,
            self.usd,
            self.rate_date_invoice,
        )
        self._assert_invoice_dual_totals(
            invoice,
            invoice_amount,
            expected_total_local,
            expected_total_reference,
        )
        self._assert_invoice_residuals(
            invoice,
            invoice_amount,
            expected_total_local,
            expected_total_reference,
        )
        self._assert_move_line_dual_fields(invoice)

        expected_document_residual = invoice_amount
        expected_reference_amounts = []
        expected_local_amounts = []

        for index, payment_values in enumerate(payments):
            payment = self._create_payment(
                invoice,
                payment_values["currency"],
                payment_values["amount"],
                payment_values["date"],
            )
            expected_document_payment = self._convert(
                payment_values["amount"],
                payment_values["currency"],
                invoice_currency,
                payment_values["date"],
            )
            expected_document_residual = max(
                0.0,
                invoice_currency.round(
                    expected_document_residual - expected_document_payment
                ),
            )
            expected_reference_amounts.append(
                self._convert(
                    payment_values["amount"],
                    payment_values["currency"],
                    self.usd,
                    payment_values["date"],
                )
            )
            expected_local_amounts.append(
                self._convert(
                    payment_values["amount"],
                    payment_values["currency"],
                    self.ves,
                    payment_values["date"],
                )
            )
            expected_local_residual = self._convert(
                expected_document_residual,
                invoice_currency,
                self.ves,
                self.rate_date_invoice,
            )
            expected_reference_residual = (
                0.0
                if invoice_currency.is_zero(expected_document_residual)
                else expected_total_reference - sum(expected_reference_amounts)
            )

            self._assert_invoice_residuals(
                invoice,
                expected_document_residual,
                expected_local_residual,
                expected_reference_residual,
            )
            self._assert_payment_widgets(
                invoice,
                expected_reference_amounts,
                expected_local_amounts,
            )
            self._assert_move_line_dual_fields(invoice)
            self._assert_partial_reference_amounts(invoice)

            self.assertAlmostEqual(
                payment.amount_local,
                expected_local_amounts[-1],
                delta=self.ves.rounding,
            )
            self.assertAlmostEqual(
                payment.amount_ref,
                expected_reference_amounts[-1],
                delta=self.usd.rounding,
            )
            if index < len(payments) - 1:
                self.assertEqual(invoice.payment_state, "partial")
            else:
                self.assertIn(invoice.payment_state, ("paid", "in_payment"))

        return invoice

    def _get_report_options(self, report_xmlid, date_to, currency=None):
        report = self.env.ref(report_xmlid)
        previous_options = {
            "selected_variant_id": report.id,
            "date": {
                "date_from": self.rate_date_invoice,
                "date_to": date_to,
                "mode": "range",
                "filter": "custom",
            },
            "show_account": True,
            "show_currency": True,
        }
        if currency:
            previous_options["dual_currency_id"] = currency.id
        return report, report.get_options(previous_options)
