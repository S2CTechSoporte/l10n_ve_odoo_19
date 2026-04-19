# -*- coding: utf-8 -*-
"""Upgrade helpers for s2c_delivery_date 19.0.1.1.0."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        _logger.info("Fresh install of s2c_delivery_date, no post-migration required")
        return

    _logger.info("Running s2c_delivery_date post-migration to 19.0.1.1.0 from %s", version)
    env = api.Environment(cr, SUPERUSER_ID, {})
    _fix_invoice_maturity_dates(env)


def _fix_invoice_maturity_dates(env):
    invoices = env['account.move'].search([
        ('state', '=', 'posted'),
        ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
        ('delivery_date', '!=', False),
        ('invoice_payment_term_id', '!=', False),
    ])

    if not invoices:
        _logger.info("No posted invoices with delivery dates found for reconciliation")
        return

    corrected = 0
    for invoice in invoices:
        receivable_lines = invoice.line_ids.filtered(
            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
        )
        if not receivable_lines:
            continue

        invoice.invalidate_recordset(['needed_terms', 'invoice_date_due'])
        invoice._compute_needed_terms()
        invoice._compute_invoice_date_due()

        maturity_dates = [
            term_key['date_maturity']
            for term_key in invoice.needed_terms.keys()
            if term_key and term_key.get('date_maturity')
        ]
        if not maturity_dates:
            continue

        target_date = max(maturity_dates)
        lines_to_fix = receivable_lines.filtered(lambda line: line.date_maturity != target_date)
        if not lines_to_fix:
            continue

        lines_to_fix.write({'date_maturity': target_date})
        corrected += 1

    _logger.info("s2c_delivery_date post-migration corrected %s invoices", corrected)