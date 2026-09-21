# Venezuela Dual Currency

`l10n_ve_dual_currency` adds a reference-currency layer to the Odoo 19.0
Venezuelan accounting localization. It is intended for companies whose local
currency is the Venezuelan bolivar soberano (VES) and whose operational
reference currency is usually USD.

## Scope

- Activates `base.VES` and assigns VES as the default currency of Venezuela.
- Adds a company-level reference currency, with USD as its default.
- Displays invoice totals, residuals, journal items, and payments in local and
  reference currencies.
- Computes reconciled reference amounts at each reconciliation date.
- Adds a VES/reference-currency selector to aged receivable and aged payable
  reports.
- Preserves the original invoice rate for local-currency credit notes created
  from an invoice.

## Dependencies

- `l10n_ve`
- `account_reports`

The Odoo 18.0 dependency `account_report_multi_currency` is intentionally not
used. The aged-report selector and reference-currency calculations are owned by
this module and use Odoo 19.0 report options.

## Configuration

1. Open Accounting settings.
2. Confirm that the company's main currency is VES.
3. Select the reference currency under **Dual Currency**.
4. Configure deterministic or live exchange rates using standard Odoo currency
   rates.

The module does not change the currency of an existing company because Odoo
must protect posted accounting data. Existing companies must select VES before
posting entries if they still use a legacy Venezuelan currency.

## Technical Design

- `res.company.fcurrency_id` stores the reference currency.
- `account.move` exposes local/reference totals and converted payment widgets.
- `account.move.line` stores converted debit, credit, balance, price, and
  residual helper fields.
- `account.partial.reconcile.amount_fcurrency` uses the reconciled amount from
  the USD side when present; otherwise it converts the company-currency amount
  at `max_date`.
- `account.aged.partner.balance.report.handler` rebuilds aged buckets from the
  stored reference balance and reconciliations up to the report cutoff date.
- `account.report._build_column_dict()` formats aged values with the selected
  VES or reference currency.

No direct SQL query against Odoo reconciliation tables is used.

## Validation

`REQUIRED_TESTS.md` is the functional acceptance contract. `TEST_PLAN.md`
defines the automated Odoo 19.0 coverage and commands for databases with and
without demo data.
