from contextlib import contextmanager

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class DualCurrencyTestCommon(AccountTestInvoicingCommon):
    country_code = "DE"
    chart_template = "generic_coa"

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
                "currency_id": cls.ves.id,
                "secondary_currency_id": cls.usd.id,
            }
        )
        cls.company_data["currency"] = cls.ves

        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.purchase_journal = cls.company_data["default_journal_purchase"]
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.misc_journal = cls.company_data["default_journal_misc"]

        cls.partner_customer = cls.env["res.partner"].create(
            {
                "name": "Dual Currency Customer",
                "country_id": cls.env.ref("base.de").id,
            }
        )
        cls.partner_vendor = cls.env["res.partner"].create(
            {
                "name": "Dual Currency Vendor",
                "country_id": cls.env.ref("base.de").id,
                "supplier_rank": 1,
            }
        )
        cls.product = cls._create_product(
            name="Dual Currency Service",
            list_price=100.0,
            taxes_id=[Command.clear()],
        )

        cls.rate_date_invoice = fields.Date.to_date("2026-01-10")
        cls.rate_date_second = fields.Date.to_date("2026-01-20")
        cls.rate_date_third = fields.Date.to_date("2026-01-30")
        cls._set_rate(cls.usd, cls.company, cls.rate_date_invoice, 50.0)
        cls._set_rate(cls.usd, cls.company, cls.rate_date_second, 52.0)
        cls._set_rate(cls.usd, cls.company, cls.rate_date_third, 54.0)

    @contextmanager
    def _assert_error(self, exception, pattern):
        """Assert an error and roll the failed operation back, like ``assertRaises``."""
        with self.assertRaisesRegex(exception, pattern):
            with self.env.cr.savepoint():
                yield

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

    def _manual_convert(self, amount, from_currency, to_currency, manual_rate):
        """Convert between VES and USD with a manual rate expressed as VES per USD."""
        if from_currency == to_currency:
            return amount
        if (from_currency, to_currency) == (self.usd, self.ves):
            return amount * manual_rate
        if (from_currency, to_currency) == (self.ves, self.usd):
            return amount / manual_rate
        raise AssertionError("A manual rate only converts between VES and USD.")

    def _convert_at(self, amount, from_currency, to_currency, rate_date, manual_rate=None):
        """Convert at the manual rate of a document, or at the system rate of a date."""
        if manual_rate:
            return self._manual_convert(amount, from_currency, to_currency, manual_rate)
        return self._convert(amount, from_currency, to_currency, rate_date)

    def _create_invoice(
        self,
        currency,
        amount,
        invoice_date,
        move_type="out_invoice",
        manual_rate=None,
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
        values = {
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
        if manual_rate:
            values.update({"manual_rate": True, "manual_conversion_rate": manual_rate})
        invoice = self.env["account.move"].create(values)
        invoice.action_post()
        return invoice

    def _create_payment(self, invoice, currency, amount, payment_date, manual_rate=None):
        values = {
            "payment_date": payment_date,
            "journal_id": self.bank_journal.id,
            "amount": amount,
            "currency_id": currency.id,
        }
        if manual_rate:
            values.update({"manual_rate": True, "manual_conversion_rate": manual_rate})
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create(values)
        payment = wizard._create_payments()
        if payment.state == "in_process":
            payment.action_validate()
        return payment

    def _create_direct_payment(
        self,
        currency,
        amount,
        payment_date,
        payment_type="outbound",
        manual_rate=None,
        post=True,
    ):
        """Create a payment of the vendor (outbound) or of the customer (inbound)."""
        partner = (
            self.partner_vendor if payment_type == "outbound" else self.partner_customer
        )
        values = {
            "payment_type": payment_type,
            "partner_type": "supplier" if payment_type == "outbound" else "customer",
            "partner_id": partner.id,
            "amount": amount,
            "date": payment_date,
            "currency_id": currency.id,
            "journal_id": self.bank_journal.id,
        }
        if manual_rate:
            values.update({"manual_rate": True, "manual_conversion_rate": manual_rate})
        payment = self.env["account.payment"].create(values)
        if post:
            payment.action_post()
        return payment

    def _create_credit_note(self, invoice, reversal_date):
        wizard = self.env["account.move.reversal"].with_context(
            active_model="account.move",
            active_ids=invoice.ids,
        ).create(
            {
                "move_ids": [(6, 0, invoice.ids)],
                "company_id": self.company.id,
                "journal_id": invoice.journal_id.id,
                "date": reversal_date,
                "reason": "Dual currency reversal test",
            }
        )
        wizard.refund_moves()
        credit_note = wizard.new_move_ids[:1]
        if credit_note.state == "draft":
            credit_note.action_post()
        return credit_note

    def _create_entry(self, items, entry_date=None, manual_rate=None, post=True, **values):
        """Create a manual journal entry from ``(account, currency, amount, values)`` items.

        The amount is expressed in the currency of the item: Odoo derives the balance of
        the items in a foreign currency from the rate of the entry. ``values`` is
        optional and completes the item.
        """
        entry_values = {
            "move_type": "entry",
            "journal_id": self.misc_journal.id,
            "date": entry_date or self.rate_date_invoice,
            "line_ids": [
                Command.create(
                    {
                        "name": account.name,
                        "account_id": account.id,
                        "currency_id": currency.id,
                        "amount_currency": amount,
                        **(item_values[0] if item_values else {}),
                    }
                )
                for account, currency, amount, *item_values in items
            ],
            **values,
        }
        if manual_rate:
            entry_values.update({"manual_rate": True, "manual_conversion_rate": manual_rate})
        entry = self.env["account.move"].create(entry_values)
        if post:
            entry.action_post()
        return entry

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
                "amount_total_secondary_currency",
                "secondary_currency_id",
            ]
        )
        self.assertEqual(invoice.secondary_currency_id, self.usd)
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
            invoice.amount_total_secondary_currency,
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
                "amount_residual_secondary_currency",
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
            invoice.amount_residual_secondary_currency,
            self._round(self.usd, expected_reference),
            delta=self.usd.rounding * 2,
        )

    def _assert_move_line_dual_fields(self, move, manual_rate=None):
        for line in move.line_ids.filtered(
            lambda candidate: candidate.display_type
            not in ("line_section", "line_subsection", "line_note")
        ):
            line.invalidate_recordset(
                [
                    "debit_secondary_currency",
                    "credit_secondary_currency",
                    "balance_secondary_currency",
                    "amount_residual_secondary_currency",
                ]
            )
            self.assertEqual(line.secondary_currency_id, self.usd)
            self.assertAlmostEqual(
                line.debit_secondary_currency - line.credit_secondary_currency,
                line.balance_secondary_currency,
                delta=self.usd.rounding,
            )

        product_line = move.invoice_line_ids[:1]
        if product_line:
            expected_subtotal = (
                self._manual_convert(
                    product_line.price_subtotal,
                    move.currency_id,
                    self.usd,
                    manual_rate,
                )
                if manual_rate
                else move.currency_id._convert(
                    product_line.price_subtotal,
                    self.usd,
                    self.company,
                    move._get_dual_currency_reference_rate_date(),
                    False,
                )
            )
            self.assertAlmostEqual(
                product_line.price_subtotal_secondary_currency,
                expected_subtotal,
                delta=self.usd.rounding,
            )

    def _assert_partial_reference_amounts(self, invoice, manual_rates=None):
        """Check the reference amount of the partials; ``manual_rates`` maps the id of a
        payment journal entry to the manual rate (VES per USD) of that payment."""
        manual_rates = manual_rates or {}
        term_line = self._get_payment_term_line(invoice)
        partials = term_line.matched_debit_ids | term_line.matched_credit_ids
        for partial in partials:
            partial.invalidate_recordset(["amount_secondary_currency"])
            if partial.debit_currency_id == self.usd:
                expected = partial.debit_amount_currency
            elif partial.credit_currency_id == self.usd:
                expected = partial.credit_amount_currency
            else:
                manual_rate = manual_rates.get(
                    partial.debit_move_id.move_id.id
                ) or manual_rates.get(partial.credit_move_id.move_id.id)
                expected = self._convert_at(
                    partial.amount,
                    self.ves,
                    self.usd,
                    partial.max_date,
                    manual_rate,
                )
            self.assertAlmostEqual(
                partial.amount_secondary_currency,
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
                "invoice_payments_widget_secondary_currency",
                "invoice_payments_widget_local_currency",
            ]
        )
        reference_widget = invoice.invoice_payments_widget_secondary_currency or {
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
        invoice_manual_rate=None,
        move_type="out_invoice",
    ):
        """Run an invoice/payments scenario at the system rates of the dates or, when a
        document has a ``manual_rate`` (VES per USD), at the manual rate of that document."""
        invoice = self._create_invoice(
            invoice_currency,
            invoice_amount,
            self.rate_date_invoice,
            move_type=move_type,
            manual_rate=invoice_manual_rate,
        )
        expected_total_local = self._convert_at(
            invoice_amount,
            invoice_currency,
            self.ves,
            self.rate_date_invoice,
            invoice_manual_rate,
        )
        expected_total_reference = self._convert_at(
            invoice_amount,
            invoice_currency,
            self.usd,
            self.rate_date_invoice,
            invoice_manual_rate,
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
        self._assert_move_line_dual_fields(invoice, manual_rate=invoice_manual_rate)

        expected_document_residual = invoice_amount
        expected_reference_amounts = []
        expected_local_amounts = []
        payment_manual_rates = {}

        for index, payment_values in enumerate(payments):
            payment_manual_rate = payment_values.get("manual_rate")
            payment = self._create_payment(
                invoice,
                payment_values["currency"],
                payment_values["amount"],
                payment_values["date"],
                manual_rate=payment_manual_rate,
            )
            if payment_manual_rate:
                payment_manual_rates[payment.move_id.id] = payment_manual_rate
            expected_document_payment = self._convert_at(
                payment_values["amount"],
                payment_values["currency"],
                invoice_currency,
                payment_values["date"],
                payment_manual_rate,
            )
            expected_document_residual = max(
                0.0,
                invoice_currency.round(
                    expected_document_residual - expected_document_payment
                ),
            )
            expected_reference_amounts.append(
                self._convert_at(
                    payment_values["amount"],
                    payment_values["currency"],
                    self.usd,
                    payment_values["date"],
                    payment_manual_rate,
                )
            )
            expected_local_amounts.append(
                self._convert_at(
                    payment_values["amount"],
                    payment_values["currency"],
                    self.ves,
                    payment_values["date"],
                    payment_manual_rate,
                )
            )
            expected_local_residual = self._convert_at(
                expected_document_residual,
                invoice_currency,
                self.ves,
                self.rate_date_invoice,
                invoice_manual_rate,
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
            self._assert_move_line_dual_fields(invoice, manual_rate=invoice_manual_rate)
            self._assert_partial_reference_amounts(invoice, payment_manual_rates)

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
