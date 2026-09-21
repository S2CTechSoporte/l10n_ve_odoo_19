# Test Plan

## Goal

Automate every requirement in `REQUIRED_TESTS.md` for Odoo 19.0 without
`account_report_multi_currency`.

## Framework

Use Odoo 19.0 `TransactionCase` behavior through
`AccountTestInvoicingCommon`. In Odoo 19 each test method already runs in a
savepoint; the legacy recommendation to subclass `SavepointCase` does not apply.

Use `@tagged("post_install", "-at_install")` because the tests post accounting
documents and exercise installed report handlers.

## Test Layout

- `tests/common.py`: Venezuelan company, VES/USD rates, journals, partners,
  products, invoice/payment helpers, and shared assertions.
- `tests/test_dual_currency_invoice_payments.py`: the mandatory ten-scenario
  matrix and payment helper fields.
- `tests/test_dual_currency_aged_reports.py`: report options, cutoff dates,
  receivable/payable buckets, totals, and report-column currency formatting.
- `tests/test_dual_currency_accounting_flows.py`: manual journal entries,
  credit notes, fallback behavior, VES activation, and dependency checks.
- `tests/test_dual_currency_demo.py`: XML demo company and rate validation.

## Shared Fixtures

The common class must configure:

1. Country `base.ve`.
2. Active currencies `base.VES` and `base.USD`.
3. Company currency VES and `company.fcurrency_id` USD.
4. Standard Odoo sale, purchase, bank, and miscellaneous journals.
5. A Venezuelan customer and vendor.
6. A tax-free service product.
7. Company-specific rates of 50, 52, and 54 VES per USD on 2026-01-10,
   2026-01-20, and 2026-01-30.

## Required Helpers

- `_set_rate(currency, company, rate_date, inverse_rate)`
- `_create_invoice(currency, amount, invoice_date, move_type="out_invoice")`
- `_create_payment(invoice, currency, amount, payment_date)`
- `_get_payment_term_line(move)`
- `_assert_invoice_dual_totals(invoice, document, local, reference)`
- `_assert_dual_residual_coherence(invoice)`
- `_assert_payment_widgets(invoice, payment_count)`
- `_assert_move_line_dual_fields(move)`
- `_run_invoice_payment_scenario(...)`
- `_get_report_options(report_xmlid, date_to, currency)`

Helpers must use standard Odoo currency conversion and payment registration
APIs instead of reproducing Odoo reconciliation logic.

## Scenario Methods

1. `test_invoice_usd_full_payment_usd`
2. `test_invoice_usd_full_payment_ves`
3. `test_invoice_ves_full_payment_usd`
4. `test_invoice_ves_full_payment_ves`
5. `test_invoice_usd_partial_payments_usd`
6. `test_invoice_usd_partial_payments_ves`
7. `test_invoice_usd_mixed_partial_payments_multi_date`
8. `test_invoice_ves_partial_payments_usd`
9. `test_invoice_ves_partial_payments_ves`
10. `test_invoice_ves_mixed_partial_payments_multi_date`

## Report Strategy

Obtain options from the standard aged report with `report.get_options()`.
Select USD by passing `dual_currency_id` in previous options. Invoke
`_aged_partner_report_custom_engine_common()` for:

- Grand total: no current groupby.
- Partner total: `current_groupby="partner_id"`.
- Journal item: `current_groupby="id"` when validating detail values.

Assert that payments whose `max_date` is later than `options.date.date_to` are
excluded from the report residual.

## Demo And Non-Demo Runs

Use the interpreter and server configured in `.vscode/launch.json`:

```bash
./.venv/bin/python /opt/odoo/19.0/odoo/odoo-bin \
    -c odoo.conf \
    -d test_l10n_ve_dual_currency_19 \
    -i l10n_ve_dual_currency \
    --without-demo=True \
    --test-enable \
    --test-tags /l10n_ve_dual_currency \
    --http-port=18019 \
    --stop-after-init
```

Run a second clean database with demo data:

```bash
./.venv/bin/python /opt/odoo/19.0/odoo/odoo-bin \
    -c odoo.conf \
    -d test_l10n_ve_dual_currency_demo_19 \
    -i l10n_ve_dual_currency \
    --with-demo \
    --test-enable \
    --test-tags /l10n_ve_dual_currency \
    --http-port=18021 \
    --stop-after-init
```

Both databases must be newly initialized so results do not depend on existing
accounting records or installed custom modules.

## Static Checks

Before the Odoo runs:

1. Compile all Python files.
2. Parse all XML files.
3. Confirm that no view contains `attrs`.
4. Confirm that no file references `l10n_cr`, Costa Rica, CRC, or
   `account_report_multi_currency` except documentation explicitly stating that
   the old dependency was removed.

## Completion Criteria

The work is complete only when:

1. All ten invoice/payment scenarios pass.
2. Aged receivable and payable tests pass in VES and USD modes.
3. Manual entries, refunds, fallback behavior, and Venezuelan currency setup
   pass.
4. The no-demo installation passes.
5. The demo installation executes and passes the demo assertions.
