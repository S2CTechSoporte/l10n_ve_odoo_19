# BCV Currency Rate Provider

## Description

Adds **[VE] Central Bank of Venezuela (BCV)** to Odoo 19's native automatic
currency-rate service. The provider retrieves the official USD quotation from
<https://www.bcv.org.ve/> and, when needed, its EUR, CNY, TRY and RUB quotations.
It updates active VES and VEF for companies using one of these foreign currencies,
or USD for companies using VES or VEF.

VEF is supported only as an alias for legacy configurations. It receives the
same current quotation as VES; no historical redenomination factor is applied.

## Context

BCV publishes bolivars per USD, whereas Odoo stores rates normalized to the
company's currency. For the illustrative quotation `871,36890000`:

| Company currency | Currency being updated | Technical `rate` |
| --- | --- | --- |
| USD | VES or VEF | `871.36890000` |
| USD | USD | `1.0` |
| VES or VEF | USD | `1 / 871.36890000` |
| VES or VEF | VES or VEF | `1.0` |
| EUR | VES or VEF | `981.17880877` |
| EUR | EUR | `1.0` |

With a bolivar company, the USD rate's `inverse_company_rate` displays
`871.36890000`. Rates are native floating-point values, not localized strings.
The EUR example uses the separate official EUR quotation `981,17880877`, not
the dollar quotation. CNY, TRY and RUB companies use their respective published
quotations in the same way. Other main currencies are rejected explicitly;
the provider does not infer unpublished quotations.

The native updater also maintains the company-currency reference at `1.0`.
VES and VEF remain unit-equivalent compatibility aliases for bolivar companies.
No other foreign currency rates are created or changed, even if they are active
or another company in the same update group uses them as its main currency.

## Installation

Install `currency_rate_bcv_provider` from the Apps menu. It depends on the
Enterprise module `currency_rate_live`, which supplies the existing settings
view, scheduler and rate-generation logic. Python dependencies `requests` and
`lxml` are already required by Odoo.

No Odoo core files are modified. Installation without demo data does not
activate currencies, select the provider for existing companies, or make
network requests.

## Configuration

1. Activate USD and VES in the currency list. Activate VEF only when legacy
   records require it, and activate the company's main currency if different.
2. Open Accounting settings for the intended company.
3. Under automatic currency rates, select **[VE] Central Bank of Venezuela
   (BCV)** as the service.
4. Choose the native manual, daily, weekly or monthly interval and next run.

The BCV request temporarily uses `verify=False`, as explicitly requested, with
a 20-second timeout. No CA-bundle configuration is required in this mode,
including on Odoo.sh. This setting applies only to requests made by the BCV
provider; it does not change other Odoo providers or globally suppress warnings.

**Security limitation:** TLS still encrypts traffic, but the server certificate
and hostname are not verified. An intercepted connection could supply false
exchange rates that pass the numeric and date checks. A trusted certificate-chain
solution with verification enabled is recommended for production.

## Usage

- **Manual:** use the existing **Update now** button, which calls
  `res.config.settings.update_currency_rates_manually()`.
- **Automatic:** the native scheduled action
  `currency_rate_live.ir_cron_currency_update` calls
  `res.company.run_update_currency()`.
- **Programmatic:** call `company.update_currency_rates()` after selecting
  `company.currency_provider = "bcv"`.

Each update uses BCV's **Fecha Valor**, not the server's current date. Refreshing
the same currency, company and value date updates the existing record instead
of creating a duplicate. Inactive currencies and currencies other than USD,
VES, VEF and the company's own reference currency are not updated.

## Development

### Extension points and scraping

[models/res_company.py](models/res_company.py) extends only `res.company`:

- `currency_provider` adds the `bcv` selection. The related settings field
  receives the option automatically; no settings view or button override is
  needed. Removing the module clears this optional provider value.
- `_parse_bcv_data(available_currencies)` is the native provider hook. It
  returns `{currency_code: (USD_based_rate, value_date)}`. For a foreign company
  currency, its USD-based rate is the USD quotation divided by that currency's
  quotation, both expressed in bolivars and for the same official value date.
- `_generate_currency_rates(parsed_data)` filters the data per BCV company:
  VES/VEF are the foreign-company destinations; USD is the bolivar-company
  destination. Company and bolivar-alias reference records are retained.
  Normalization, company-specific writes and duplicate handling remain native
  `currency_rate_live` behavior. Other providers receive unfiltered data.
- `_extract_bcv_rate(content, currency_code="USD")` locates the requested BCV
  block (`dolar`, `euro`, `yuan`, `lira` or `rublo`) and its single `strong`
  quotation, accepts a decimal comma and optional dot thousands separators,
  and validates a finite, strictly positive value. It reads the ISO `content`
  attribute of the `date-display-single` span in the closest `views-row`
  ancestor of the currency block. Unrelated dates outside that block are ignored.
  Existing callers that omit the currency code still extract USD.

Missing or ambiguous markup, malformed values, invalid dates and HTTP/TLS
errors raise `UserError`. Manual failures are shown to the user. Scheduled
failures use native warning logging and retain the native scheduling behavior:
the next execution date advances even if the request fails. Existing providers
and country-based defaults are unchanged.

No new models, access controls, menus or production cron records are introduced.
Existing Odoo settings permissions and company-rate isolation remain in effect.
Future BCV markup changes may require updating the validated XPath selectors.

### Translations

[i18n/es_419.po](i18n/es_419.po) translates the provider option and errors into
Latin American Spanish, including the `es_VE` fallback. Occurrences follow the
Odoo 19 exporter. Tests validate the native PO reader, the option in both
company/settings fields, and a localized validation error.

### Demo data

[demo/bcv_provider_demo.xml](demo/bcv_provider_demo.xml) activates USD, VES and
VEF only when demo data is enabled, and creates a USD company configured for
manual BCV updates. Its three rates use the illustrative `871.36890000`
quotation dated `2026-10-05`; they are test fixtures, not independently verified
historical quotations. Demo installation never fetches live rates.

### Tests

[tests/test_bcv_provider.py](tests/test_bcv_provider.py) creates its own company
fixtures and covers scraping, decimal precision, dates, required currencies,
manual updates, native scheduling, VES/VEF normalization, idempotency,
all seven supported company currencies, USD cross-rates, unchanged unrelated
rates, company isolation, unchanged existing providers and validation/network
failures. Missing or invalid company quotations and mismatched official dates
are rejected before writing any company in the provider group.
[tests/test_bcv_demo.py](tests/test_bcv_demo.py) separately validates manifest
demo records and their manual and scheduled updates. All HTTP requests are
mocked using [tests/fixtures/bcv_rates.html](tests/fixtures/bcv_rates.html).
Demo tests also switch the declared demo company to EUR and VES to validate
both destination rules without adding scheduled production records.

Run from the workspace root using the launch configuration's environment and
two new, disposable databases:

```sh
export VIRTUAL_ENV="$PWD/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
export TMPDIR="$PWD/tmp"
export PYDEVD_DISABLE_FILE_VALIDATION=1

./.venv/bin/python -B /opt/odoo/19.0/odoo/odoo-bin \
    -c odoo.conf -d test_bcv_nodemo -i currency_rate_bcv_provider \
    --without-demo=True --test-tags /currency_rate_bcv_provider \
    --no-http --http-port=0 --workers=0 --max-cron-threads=0 \
    --stop-after-init --logfile=

./.venv/bin/python -B /opt/odoo/19.0/odoo/odoo-bin \
    -c odoo.conf -d test_bcv_demo -i currency_rate_bcv_provider \
    --with-demo --test-tags /currency_rate_bcv_provider \
    --no-http --http-port=0 --workers=0 --max-cron-threads=0 \
    --stop-after-init --logfile=
```

Demo tests are intentionally skipped in the database initialized without demo
data. To rerun an initialized test database, replace `-i` with `-u`.

## Contributors

- Juan Córdoba <jgcordobac@gmail.com>
