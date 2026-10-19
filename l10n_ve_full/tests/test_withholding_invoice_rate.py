from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestWithholdingInvoiceRate(AccountTestInvoicingCommon):
    """The withholdings of an invoice take the rate of the invoice.

    The rate is the standard ``invoice_currency_rate`` of Odoo. A draft invoice gets it
    edited by hand here, exactly as an accountant (or any other module) does, so these
    tests do not need any module that captures the rate. Every rate is the number of
    units of the invoice currency per unit of the company currency.
    """

    country_code = 'DE'
    chart_template = 'generic_coa'
    company_currency_code = 'USD'
    foreign_currency_code = 'VES'
    # Rate of the table and rate of the invoice, which differ on purpose.
    system_rate = 800.0
    invoice_rate = 880.0
    # Untaxed amount of the invoice, in its own currency.
    foreign_base = 88000.0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        # The withholding documents are managed by the users of the localization.
        cls.env.user.group_ids |= cls.env.ref('l10n_ve_full.group_localizacion')
        cls.company_currency = cls.env.ref('base.%s' % cls.company_currency_code)
        cls.foreign_currency = cls.env.ref('base.%s' % cls.foreign_currency_code)
        (cls.company_currency | cls.foreign_currency).active = True
        cls.company.currency_id = cls.company_currency
        cls.invoice_date = fields.Date.to_date('2026-01-10')
        cls.env['res.currency.rate'].search([
            ('currency_id', '=', cls.foreign_currency.id),
            ('company_id', '=', cls.company.id),
        ]).unlink()
        cls.env['res.currency.rate'].create({
            'company_id': cls.company.id,
            'currency_id': cls.foreign_currency.id,
            'name': cls.invoice_date,
            'rate': cls.system_rate,
        })

        # The test creates the withholding documents itself: posting an invoice must not
        # create them by agent flags.
        cls.customer = cls.env['res.partner'].create({
            'name': 'Withholding Customer', 'country_id': cls.env.ref('base.de').id,
            'wh_iva_agent': False, 'islr_withholding_agent': False,
        })
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Withholding Vendor', 'country_id': cls.env.ref('base.de').id,
            'wh_iva_agent': False, 'islr_withholding_agent': False,
        })
        tax_group = cls.env['account.tax.group'].create({'name': 'Withholding Test Group'})
        cls.sale_vat, cls.purchase_vat = cls.env['account.tax'].create([
            {
                'name': 'Withholding VAT 16%% %s' % usage,
                'amount_type': 'percent',
                'amount': 16.0,
                'type_tax_use': usage,
                'tax_group_id': tax_group.id,
                'type_tax': 'iva',
                'appl_type': 'general',
            }
            for usage in ('sale', 'purchase')
        ])
        cls.receivable = cls.company_data['default_account_receivable']
        cls.payable = cls.company_data['default_account_payable']
        cls.vat_account = cls.env['account.account'].create({
            'name': 'VAT withheld',
            'code': 'WH.VAT.1',
            'account_type': 'liability_current',
        })
        cls.wh_journal = cls.env['account.journal'].create({
            'name': 'VAT withholding',
            'code': 'RIVT',
            'type': 'general',
            'company_id': cls.company.id,
            'is_iva_journal': True,
            'default_iva_account': cls.vat_account.id,
        })

    # ---------------------------------------------------------------- helpers

    def _create_invoice(self, move_type='out_invoice', invoice_rate=None, partner=None):
        """Post an invoice in the foreign currency; ``invoice_rate`` is edited by hand."""
        is_customer = move_type.startswith('out_')
        invoice = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': (partner or (self.customer if is_customer else self.vendor)).id,
            'invoice_date': self.invoice_date,
            'date': self.invoice_date,
            'journal_id': (self.company_data['default_journal_sale']
                           if is_customer else self.company_data['default_journal_purchase']).id,
            'currency_id': self.foreign_currency.id,
            'invoice_line_ids': [Command.create({
                'name': 'Service',
                'quantity': 1.0,
                'price_unit': self.foreign_base,
                'tax_ids': [Command.set((self.sale_vat if is_customer else self.purchase_vat).ids)],
            })],
        })
        if invoice_rate:
            invoice.invoice_currency_rate = invoice_rate
        invoice.action_post()
        return invoice

    def _company_amount(self, foreign_amount, rate=None):
        """Amount of the foreign currency in the company currency, at a rate."""
        return self.company_currency.round(foreign_amount / (rate or self.invoice_rate))

    def _create_vat_withholding(self, invoice):
        """Return the tax line of a VAT withholding document of the invoice (75% retained)."""
        is_customer = invoice.move_type.startswith('out_')
        retention = self.env['account.wh.iva'].create({
            'name': 'VAT withholding of %s' % invoice.name,
            'type': invoice.move_type,
            'partner_id': invoice.partner_id.id,
            'account_id': (self.receivable if is_customer else self.payable).id,
            'journal_id': self.wh_journal.id,
            'date_ret': invoice.date,
            'date': invoice.date,
        })
        line = self.env['account.wh.iva.line'].create({
            'name': 'VAT withholding line',
            'retention_id': retention.id,
            'invoice_id': invoice.id,
            'wh_iva_rate': 75.0,
        })
        tax_line = self.env['account.wh.iva.line.tax'].create({
            'wh_vat_line_id': line.id,
            'id_tax': invoice.invoice_line_ids.tax_ids.id,
            'move_id': invoice.id,
            'base': invoice.amount_untaxed,
            'amount': invoice.amount_tax,
        })
        return tax_line

    # --------------------------------------------------------- conversion helpers

    def test_module_does_not_depend_on_the_dual_currency_module(self):
        """The withholdings only use standard fields of Odoo: the modules are independent."""
        module = self.env['ir.module.module'].search([('name', '=', 'l10n_ve_full')])
        self.assertTrue(module)
        self.assertNotIn('accounting_dual_currency', module.dependencies_id.mapped('name'))

    def test_conversions_use_the_rate_of_the_invoice(self):
        system = self._create_invoice()
        manual = self._create_invoice(invoice_rate=self.invoice_rate)
        self.assertAlmostEqual(system.invoice_currency_rate, self.system_rate)
        self.assertAlmostEqual(manual.invoice_currency_rate, self.invoice_rate)
        for invoice, rate in ((system, self.system_rate), (manual, self.invoice_rate)):
            with self.subTest(rate=rate):
                self.assertAlmostEqual(
                    invoice._wh_to_company_currency(self.foreign_base),
                    self._company_amount(self.foreign_base, rate),
                )
                self.assertAlmostEqual(
                    invoice._wh_from_company_currency(self._company_amount(self.foreign_base, rate)),
                    self.foreign_base,
                    delta=self.foreign_currency.rounding * rate,
                )

    def test_conversions_of_an_invoice_in_the_company_currency_keep_the_amount(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': self.invoice_date,
            'currency_id': self.company_currency.id,
            'invoice_line_ids': [Command.create({
                'name': 'Service', 'quantity': 1.0, 'price_unit': 123.456, 'tax_ids': [Command.clear()],
            })],
        })
        self.assertEqual(invoice._wh_to_company_currency(123.456), 123.456)
        self.assertEqual(invoice._wh_from_company_currency(123.456), 123.456)
        self.assertEqual(
            invoice._wh_get_line_currency_vals(123.456),
            {'currency_id': self.company_currency.id},
        )

    def test_conversions_without_a_rate_fall_back_to_the_rate_of_the_date(self):
        entry = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.company_data['default_journal_misc'].id,
            'date': self.invoice_date,
            'invoice_date': self.invoice_date,
            'currency_id': self.foreign_currency.id,
        })
        self.assertFalse(entry.invoice_currency_rate)
        self.assertAlmostEqual(
            entry._wh_to_company_currency(self.foreign_base),
            self._company_amount(self.foreign_base, self.system_rate),
        )
        self.assertEqual(
            entry._wh_get_line_currency_vals(100.0),
            {'currency_id': self.company_currency.id},
        )

    def test_line_currency_vals_are_expressed_at_the_rate_of_the_invoice(self):
        invoice = self._create_invoice(invoice_rate=self.invoice_rate)
        for balance in (12.0, -12.0):
            with self.subTest(balance=balance):
                vals = invoice._wh_get_line_currency_vals(balance)
                self.assertEqual(vals['currency_id'], self.foreign_currency.id)
                self.assertAlmostEqual(
                    vals['amount_currency'],
                    self.foreign_currency.round(balance * self.invoice_rate),
                )

    # -------------------------------------------------------- VAT withholding

    def test_vat_withholding_amounts_use_the_rate_of_the_invoice(self):
        for move_type in ('out_invoice', 'in_invoice'):
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type, invoice_rate=self.invoice_rate)
                tax_line = self._create_vat_withholding(invoice)
                # The rate of the table of the date (800) would give another amount.
                self.assertAlmostEqual(
                    tax_line.base, self._company_amount(invoice.amount_untaxed), places=2)
                self.assertAlmostEqual(
                    tax_line.amount, self._company_amount(invoice.amount_tax), places=2)
                self.assertAlmostEqual(tax_line.amount_ret, tax_line.amount * 0.75, places=2)
                self.assertNotAlmostEqual(
                    tax_line.base, self._company_amount(invoice.amount_untaxed, self.system_rate),
                    places=2)

    def test_vat_withholding_of_an_invoice_in_the_company_currency_is_not_converted(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': self.invoice_date,
            'date': self.invoice_date,
            'currency_id': self.company_currency.id,
            'invoice_line_ids': [Command.create({
                'name': 'Service', 'quantity': 1.0, 'price_unit': 100.0,
                'tax_ids': [Command.set(self.sale_vat.ids)],
            })],
        })
        invoice.action_post()
        tax_line = self._create_vat_withholding(invoice)
        self.assertAlmostEqual(tax_line.base, 100.0)
        self.assertAlmostEqual(tax_line.amount, 16.0)

    def _withhold_vat(self, invoice):
        tax_line = self._create_vat_withholding(invoice)
        is_customer = invoice.move_type.startswith('out_')
        move = invoice.ret_and_reconcile(
            abs(tax_line.amount_ret),
            self.receivable if is_customer else self.payable,
            self.wh_journal.id,
            False,
            False,
            invoice.date,
            'COMP. RET. IVA',
            tax_line,
            'wh_iva',
        )
        return tax_line, move

    def test_vat_withholding_entry_is_expressed_at_the_rate_of_the_invoice(self):
        for move_type, direction in (('out_invoice', -1), ('in_invoice', 1)):
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type, invoice_rate=self.invoice_rate)
                tax_line, move = self._withhold_vat(invoice)
                withheld = tax_line.amount_ret
                self.assertEqual(move.state, 'posted')
                self.assertEqual(len(move.line_ids), 2)
                for line in move.line_ids:
                    self.assertEqual(line.currency_id, self.foreign_currency)
                    self.assertAlmostEqual(abs(line.balance), withheld, places=2)
                    self.assertAlmostEqual(
                        abs(line.amount_currency),
                        self.foreign_currency.round(withheld * self.invoice_rate),
                    )
                    # The amount in currency has the sign of the balance.
                    self.assertGreater(line.amount_currency * line.balance, 0)
                settled_line = move.line_ids.filtered(
                    lambda line: line.account_id in (self.receivable | self.payable))
                self.assertAlmostEqual(settled_line.balance, direction * withheld, places=2)

    def test_vat_withholding_settles_the_invoice_without_exchange_difference(self):
        for move_type in ('out_invoice', 'in_invoice'):
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type, invoice_rate=self.invoice_rate)
                tax_line, move = self._withhold_vat(invoice)
                withheld_foreign = self.foreign_currency.round(tax_line.amount_ret * self.invoice_rate)
                partials = (invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids)
                self.assertEqual(len(partials), 1)
                self.assertFalse(partials.exchange_move_id)
                self.assertEqual(invoice.payment_state, 'partial')
                self.assertAlmostEqual(
                    invoice.amount_residual,
                    invoice.amount_total - withheld_foreign,
                    delta=self.foreign_currency.rounding * self.invoice_rate,
                )

    def test_vat_withholding_of_a_system_rate_invoice_uses_its_rate_too(self):
        invoice = self._create_invoice()
        tax_line, move = self._withhold_vat(invoice)
        self.assertAlmostEqual(
            tax_line.base, self._company_amount(invoice.amount_untaxed, self.system_rate), places=2)
        self.assertFalse(
            (invoice.line_ids.matched_debit_ids | invoice.line_ids.matched_credit_ids)
            .exchange_move_id)
        self.assertEqual(invoice.payment_state, 'partial')

    def test_vat_withholding_entry_of_an_invoice_in_the_company_currency_keeps_company_currency(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': self.invoice_date,
            'date': self.invoice_date,
            'currency_id': self.company_currency.id,
            'invoice_line_ids': [Command.create({
                'name': 'Service', 'quantity': 1.0, 'price_unit': 100.0,
                'tax_ids': [Command.set(self.sale_vat.ids)],
            })],
        })
        invoice.action_post()
        _tax_line, move = self._withhold_vat(invoice)
        self.assertEqual(move.line_ids.currency_id, self.company_currency)
        self.assertEqual(invoice.payment_state, 'partial')


@tagged('post_install', '-at_install')
class TestIslrWithholdingInvoiceRate(TestWithholdingInvoiceRate):
    """The income tax (ISLR) withholding of an invoice takes the rate of the invoice too."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The customer withholds the income tax; the company does not, so posting the
        # invoice does not create the withholding by itself.
        cls.company.partner_id.islr_withholding_agent = False
        cls.islr_customer = cls.env['res.partner'].create({
            'name': 'ISLR Withholding Customer',
            'country_id': cls.env.ref('base.de').id,
            'wh_iva_agent': False,
            'islr_withholding_agent': True,
        })
        cls.concept = cls.env['account.wh.islr.concept'].create({'name': 'ISLR rate test concept'})

    def _create_islr_withholding(self, invoice_rate):
        """Return the document, the invoice of the document and its concept line."""
        invoice = self._create_invoice('out_invoice', invoice_rate=invoice_rate, partner=self.islr_customer)
        invoice.invoice_line_ids.concept_id = self.concept
        document = self.env['account.wh.islr.doc'].create({
            'name': 'ISLR withholding of %s' % invoice.name,
            'type': 'out_invoice',
            'partner_id': invoice.partner_id.id,
            'journal_id': self.wh_journal.id,
            'company_id': self.company.id,
            'currency_id': self.company_currency.id,
            'date_ret': invoice.date,
            'date_uid': invoice.date,
        })
        document_invoice = self.env['account.wh.islr.doc.invoices'].create({
            'invoice_id': invoice.id,
            'islr_wh_doc_id': document.id,
        })
        line = self.env['account.wh.islr.doc.line'].create({
            'name': 'ISLR concept line',
            'invoice_id': invoice.id,
            'islr_wh_doc_id': document.id,
            'concept_id': self.concept.id,
            'iwdi_id': document_invoice.id,
        })
        return document, document_invoice, line

    def _compute_islr_withholding(self, document_invoice, line):
        # Rate of the concept: 100% of the base, 10% withheld, no subtrahend.
        rate = (100.0, 0.0, 10.0, 0.0, 'CODE', False, False, False)
        with patch.object(type(document_invoice), '_get_rate', return_value=rate):
            document_invoice._get_wh(line, self.concept.id)

    def test_islr_base_uses_the_rate_of_the_invoice(self):
        _document, document_invoice, line = self._create_islr_withholding(self.invoice_rate)
        invoice = line.invoice_id
        self._compute_islr_withholding(document_invoice, line)
        expected_base = self._company_amount(invoice.amount_untaxed)
        self.assertAlmostEqual(line.base_amount, expected_base, places=2)
        self.assertAlmostEqual(line.amount, expected_base * 0.10, places=2)
        self.assertNotAlmostEqual(
            line.base_amount,
            self._company_amount(invoice.amount_untaxed, self.system_rate),
            places=2,
        )

    def test_islr_amounts_in_the_invoice_currency_use_the_rate_of_the_invoice(self):
        _document, document_invoice, line = self._create_islr_withholding(self.invoice_rate)
        invoice = line.invoice_id
        self._compute_islr_withholding(document_invoice, line)
        amounts = document_invoice.get_amount_all(document_invoice)[document_invoice.id]
        self.assertAlmostEqual(
            amounts['currency_base_ret'],
            invoice._wh_from_company_currency(line.base_amount),
            places=2,
        )
        self.assertAlmostEqual(
            amounts['currency_amount_islr_ret'],
            invoice._wh_from_company_currency(line.base_amount * 0.10),
            places=2,
        )
        self.assertAlmostEqual(
            amounts['currency_base_ret'],
            self.foreign_currency.round(line.base_amount * self.invoice_rate),
            places=2,
        )

    def test_islr_voucher_total_uses_the_rate_of_the_invoice(self):
        document, _document_invoice, line = self._create_islr_withholding(self.invoice_rate)
        invoice = line.invoice_id
        document.state = 'done'
        values = self.env['report.l10n_ve_full.template_wh_islr']._get_report_values(document.ids)
        self.assertAlmostEqual(
            values['total_doc'], self._company_amount(invoice.amount_total), places=2)

    def test_islr_voucher_total_of_an_invoice_in_the_company_currency_is_not_converted(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.islr_customer.id,
            'invoice_date': self.invoice_date,
            'date': self.invoice_date,
            'currency_id': self.company_currency.id,
            'invoice_line_ids': [Command.create({
                'name': 'Service', 'quantity': 1.0, 'price_unit': 100.0, 'tax_ids': [Command.clear()],
            })],
        })
        invoice.action_post()
        document = self.env['account.wh.islr.doc'].create({
            'name': 'ISLR withholding of %s' % invoice.name,
            'type': 'out_invoice',
            'partner_id': invoice.partner_id.id,
            'journal_id': self.wh_journal.id,
            'company_id': self.company.id,
            'currency_id': self.company_currency.id,
            'date_ret': invoice.date,
            'date_uid': invoice.date,
        })
        self.env['account.wh.islr.doc.invoices'].create({
            'invoice_id': invoice.id, 'islr_wh_doc_id': document.id,
        })
        document.state = 'done'
        values = self.env['report.l10n_ve_full.template_wh_islr']._get_report_values(document.ids)
        self.assertAlmostEqual(values['total_doc'], 100.0)


@tagged('post_install', '-at_install')
class TestWithholdingInvoiceRateVesCompany(TestWithholdingInvoiceRate):
    """The same withholdings in a company whose currency is the foreign one of the other."""

    # Odoo only runs the test methods defined in a class unless it is told otherwise.
    allow_inherited_tests_method = True
    company_currency_code = 'VES'
    foreign_currency_code = 'USD'
    system_rate = 1 / 800.0
    invoice_rate = 1 / 880.0
    foreign_base = 100.0
