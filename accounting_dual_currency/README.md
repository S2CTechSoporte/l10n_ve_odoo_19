# Accounting Dual Currency

`accounting_dual_currency` adds a reference-currency layer to the Odoo 19.0
accounting application. It does not depend on a country localization: the
company currency can be any currency configured in Odoo, and the reference
currency is selected independently for each company. The demo uses EUR/USD;
the main accounting test matrix uses company/reference currencies (CCY/USD).

## Scope

- Adds a company-level reference currency. USD is suggested when the company
  currency is not USD; companies using USD select their reference currency.
- Displays invoice totals, taxes, and residuals in the reference currency when
  a document uses the company currency, or in the company currency for
  foreign-currency documents. Journal items expose reference amounts, and
  payment forms show amounts in both currencies.
- Computes reconciled reference amounts at each reconciliation date.
- Adds a company/reference-currency selector to aged receivable and aged
  payable reports.
- Adds the same currency choice to Partner Ledger, Balance Sheet, and Customer
  Statement, using stored reference-currency journal amounts for totals and
  drill-down lines.
- Opens Customer Statement in the currency selected in Aged Receivable or Aged
  Payable; opening it directly from the customer list defaults to the company
  currency.
- Preserves the original invoice rate for company-currency credit notes created
  from an invoice.
- Displays one USD in the counterpart currency in the navbar, immediately
  before the company selector.

## Configuration

1. Open Accounting settings.
2. Confirm the company's main currency before posting accounting entries.
3. Select the reference currency under **Dual Currency**.
4. Configure deterministic or live exchange rates using standard Odoo currency
   rates. Keep USD rates available even when neither the company nor the
   reference currency is USD, because the navbar always quotes USD.

The manifest depends on `account_reports` for its report extensions and
`currency_rate_live` for Odoo's standard provider-based rate updater. Odoo
installs both dependencies with this module. Configure a provider in Accounting
settings to use the navbar's **Update Now** action. It refreshes all active
currencies supported by that provider, not just the reference currency. It does
not enable scheduled updates or change the configured interval.

The module does not change the currency of an existing company because Odoo
must protect posted accounting data. For companies already using USD, choose a
different reference currency explicitly. Installing the module does not
activate additional currencies or alter any country's default currency.

## Usage

Invoice, journal-entry, and payment forms display a read-only **USD Rate** when
USD is the company or reference currency. This presentation derives only from
the document's saved `conversion_rate`: it never selects a date or looks up a
currency rate. With USD as reference, the saved value already expresses the
cost of one dollar in the company currency. With a USD company and a different
reference currency, its reciprocal expresses the cost of one dollar in that
reference currency. The invoice/payment transaction currency does not affect
this presentation.

If neither configured currency is USD, or no reference currency is configured,
the forms retain the saved value under **Reference Rate**, formatted in the
company currency. A USD quotation cannot be reconstructed from that saved rate
alone. The original `conversion_rate` and the journal-item reference-rate
fields retain their company-units-per-reference-unit meaning.

The navbar quotation is independent of those document rates: it always starts
with **USD** and expresses the value of one dollar. The counterpart is the
company currency unless the company uses USD, in which case it is the reference
currency. If neither configured currency is USD, the company currency is used.
The amount follows the user's language and the counterpart currency's decimal
precision and symbol position.

| Company currency | Reference currency | Navbar counterpart |
|---|---|---|
| USD | EUR | EUR |
| EUR | USD, GBP, or EUR | EUR |
| USD | USD | USD, with a unit quotation |
| Any | Not configured | The navbar item is hidden |

The quotation reads stored rates for the current date when the component loads,
its dropdown opens, or the active company changes. Reading the quotation does
not contact a rate provider. **Update Now** updates Odoo's shared currency-rate
records and then reloads the quotation; it does not redefine document reference
rates or their date rules.

In the Aged Receivable, Aged Payable, Partner Ledger, Balance Sheet, or Customer
Statement report, select the company or reference currency in the currency
dropdown. Partner Ledger and Customer Statement amounts, balances, initial
balances, and reconciled entries, and Balance Sheet account/group totals use
the selected currency. The original document's Amount Currency column remains
in its transaction currency. From an aged-report partner row, Customer
Statement inherits the selected currency for customers and vendors; the
dropdown can then change it. When selected companies do not share the same
company and reference currencies, the dropdown is hidden in Partner Ledger,
Balance Sheet, and Customer Statement.

## Technical Design

- `res.company.secondary_currency_id` stores the reference currency.
- [`res.company`](models/res_company.py) exposes the active company's navbar
  data by converting one `base.USD` unit into the counterpart currency using
  native `_convert` and language-aware monetary formatting. The quotation uses
  the current date in the user's context. Native company/root-company rate
  selection and missing-rate fallbacks are preserved.
  No reference currency means no navbar item.
- The [navbar component](static/src/components/secondary_currency_menu/secondary_currency_menu.js)
  refreshes on opening its dropdown, after updating, and on active-company
  changes. A navbar extension anchors it before the company selector because
  Studio and that selector use the same systray sequence.
  The bill and manual-refresh icons use Odoo's native `--link-color` variable
  to follow the light/dark theme without hard-coded colors.
- `update_secondary_currency_rates()` authorizes only Settings administrators
  and Accounting managers, checks the active company's access, and then
  elevates only the transient settings call to
  `res.config.settings.update_currency_rates_manually()`. Rates belong to the
  root company for branches. Other users can view the rate but cannot update.
  Provider errors propagate through Odoo's normal error dialog.
- `account.move` stores the reference rate and exposes local/reference totals
  and converted payment widgets. Its form uses separate monetary presentation
  fields to orient that saved rate toward USD without changing it.
- `account.payment` uses the same stored-rate presentation in its form.
- `account.move.line` stores converted debit, credit, balance, price, and
  residual helper fields.
- `account.partial.reconcile.amount_secondary_currency` uses the reconciled amount from
  the reference-currency side when present; otherwise it converts the
  company-currency amount at `max_date`.
- `account.aged.partner.balance.report.handler` rebuilds aged buckets from the
  stored reference balance and reconciliations up to the report cutoff date.
  Its `open_customer_statement` action passes the selected currency to the
  Customer Statement options.
- [`account.report`](models/account_report.py) selects stored secondary debit,
  credit, balance, and reconciled amounts in Partner Ledger and Customer
  Statement queries and the Balance Sheet domain engine only when the reference
  currency is selected.
  Report totals therefore retain each journal entry's own reference rate
  rather than converting the company total at the report date. It also formats
  monetary columns in the selected currency. `get_report_information()` sets
  this context before computing expression totals, so Balance Sheet group
  totals and drill-down lines use the same currency.
- The [report filters](static/src/components/aged_partner_balance/filters.xml)
  share one currency dropdown across the five reports.

The module does not run separate SQL against reconciliation tables; it reuses
Odoo's Partner Ledger queries and the stored partial-reconciliation amounts.

### Stored Document Rate Presentation

[`res.company._get_conversion_rate_display()`](models/res_company.py) shares
the orientation rule between invoices/journal entries and payments. It returns
the value, display currency, and USD/reference-label flag. Non-positive stored
rates raise a `UserError` when their reciprocal would be needed.

Both models expose non-stored `conversion_rate_display`,
`conversion_rate_display_currency_id`, and `conversion_rate_display_is_usd`.
The native monetary widget uses the display currency's precision and symbol
position, with the user's number formatting. These fields follow changes to
the saved rate; they do not introduce a separate historical snapshot or change
the original rate computation's dependencies or credit-note behavior.

The document display differs from the navbar: the latter reads native rates
for the current date. A historical document and the navbar can therefore show
different USD quotations. The journal-item rate columns keep **Reference Rate**
and their existing semantics; this change is limited to the main document and
payment form rate indicators.

### Navbar Data Contract

`get_secondary_currency_systray()` returns `False` when the active company has
no reference currency. Otherwise, its response contains:

| Key | Meaning |
|---|---|
| `currency_name` | The base currency code from `base.USD`, not the counterpart code. |
| `amount` | The unrounded result of converting one USD into the counterpart. |
| `formatted_amount` | That amount formatted by `formatLang` using the counterpart's precision, symbol position, and the user's language. |
| `can_update` | Whether the user belongs to Settings administrators or Accounting managers. |

Formatting rounds only the displayed amount; it does not round the returned
`amount`. Missing rates retain Odoo's native conversion fallbacks, so displaying
a quotation does not guarantee that a recent provider rate has been fetched.

## Existing Installations

The [19.0.1.1.0 pre-migration](migrations/19.0.1.1.0/pre-migrate.py) renames
persisted `fcurrency` columns and the due-date index to their
`secondary_currency` names when upgrading this same technical module. It does
not transfer installation or external-ID metadata from a differently named
predecessor.

Changing a module's technical name is not an in-place upgrade. Before
replacing an installed predecessor, migrate the installed-module and external
ID metadata and review its existing views and data in a database copy. The
tests below cover clean installations, not migration of installed databases.

## Validation

[Testing](TESTING.md) defines the functional acceptance contract, automated
Odoo 19.0 coverage, and commands
for databases with and without demo data. CCY/USD test fixtures run with a
generic chart of accounts, while the EUR/USD demo and invoice/payment test
verify a concrete company-currency example.
A USD/EUR invoice/payment test verifies a non-USD reference currency.
The [report tests](tests/test_dual_currency_aged_reports.py) cover Partner
Ledger totals, initial balances, indirect reconciliations and expansion, plus
Balance Sheet assets/liabilities/equity and Customer Statement balances in
both currencies, including its direct action and aged-report navigation.
