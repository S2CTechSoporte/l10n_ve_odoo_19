# -*- coding: utf-8 -*-
"""Normalize legacy Venezuelan RIF values to the compact format."""

import logging


_logger = logging.getLogger(__name__)

LEGACY_RIF_PATTERN = r'^[VEJGC]-(?:[0-9]{8}-[0-9]|[0-9]{2}\.[0-9]{3}\.[0-9]{3}-[0-9])$'
RIF_TABLES = ('res_partner', 'res_company', 'account_move', 'sale_order', 'purchase_order')


def migrate(cr, version):
    """Normalize stored RIF values with SQL, bypassing ORM fiscal data locks."""
    if not version:
        _logger.info("Fresh install of l10n_ve_full, no RIF migration required")
        return

    _logger.info("Normalizing legacy RIF formats in l10n_ve_full from %s", version)
    updated_rows = {}

    cr.execute(
        """
        UPDATE res_partner
           SET vat = regexp_replace(upper(vat), '[-.]', '', 'g')
         WHERE vat ~* %s
        """,
        [LEGACY_RIF_PATTERN],
    )
    updated_rows['res_partner.vat'] = cr.rowcount

    for table_name in RIF_TABLES:
        cr.execute(
            f"""
            UPDATE {table_name}
               SET rif = regexp_replace(upper(rif), '[-.]', '', 'g')
             WHERE rif ~* %s
            """,
            [LEGACY_RIF_PATTERN],
        )
        updated_rows[f'{table_name}.rif'] = cr.rowcount

    _logger.info("Normalized legacy RIF values: %s", updated_rows)