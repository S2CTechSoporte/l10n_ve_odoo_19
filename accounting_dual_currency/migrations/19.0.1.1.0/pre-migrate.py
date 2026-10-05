from odoo.tools import SQL


_COLUMN_RENAMES = {
    "res_company": ("fcurrency_id",),
    "res_config_settings": ("fcurrency_id",),
    "account_move": (
        "fcurrency_id",
        "amount_untaxed_fcurrency",
        "amount_tax_fcurrency",
        "amount_total_fcurrency",
        "amount_residual_fcurrency",
        "amount_total_signed_fcurrency",
        "invoice_payments_widget_fcurrency",
    ),
    "account_move_line": (
        "fcurrency_id",
        "debit_fcurrency",
        "credit_fcurrency",
        "price_unit_fcurrency",
        "price_subtotal_fcurrency",
        "amount_residual_fcurrency",
        "balance_fcurrency",
        "date_maturity_fcurrency",
    ),
    "account_partial_reconcile": (
        "company_fcurrency_id",
        "amount_fcurrency",
    ),
    "account_payment": ("fcurrency_id",),
}
_INDEX_RENAMES = (
    (
        "account_move_line__date_maturity_fcurrency_index",
        "account_move_line__date_maturity_secondary_currency_index",
    ),
)


def migrate(cr, version):
    for table, old_columns in _COLUMN_RENAMES.items():
        cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s",
            (table,),
        )
        existing_columns = {row[0] for row in cr.fetchall()}
        for old_column in old_columns:
            new_column = old_column.replace("fcurrency", "secondary_currency")
            if old_column in existing_columns and new_column not in existing_columns:
                cr.execute(
                    SQL(
                        "ALTER TABLE %s RENAME COLUMN %s TO %s",
                        SQL.identifier(table),
                        SQL.identifier(old_column),
                        SQL.identifier(new_column),
                    )
                )
                existing_columns.remove(old_column)
                existing_columns.add(new_column)

    for old_index, new_index in _INDEX_RENAMES:
        cr.execute(
            "SELECT to_regclass(%s), to_regclass(%s)",
            (old_index, new_index),
        )
        old_index_exists, new_index_exists = cr.fetchone()
        if old_index_exists and not new_index_exists:
            cr.execute(
                SQL(
                    "ALTER INDEX %s RENAME TO %s",
                    SQL.identifier(old_index),
                    SQL.identifier(new_index),
                )
            )