{
    "name": "BCV Currency Rate Provider",
    "summary": "Update bolivar exchange rates from the Central Bank of Venezuela",
    "description": (
        "Adds the Central Bank of Venezuela to the native currency-rate service. "
        "Updates VES and legacy VEF for companies using USD, EUR, CNY, TRY or RUB, "
        "and USD for bolivar companies, using official BCV quotations and value "
        "dates through manual updates or the existing scheduler."
    ),
    "author": "Juan Córdoba <jgcordobac@gmail.com>",
    "license": "LGPL-3",
    "category": "Accounting/Accounting",
    "version": "19.0.1.1.0",
    "depends": [
        "currency_rate_live",
    ],
    "demo": [
        "demo/bcv_provider_demo.xml",
    ],
    "installable": True,
}
