# -*- coding: utf-8 -*-
# Libro mayor y balance general
import json

from odoo import models, fields, api, _
from odoo.tools.misc import format_date
from odoo.tools import get_lang
from odoo.exceptions import UserError

from datetime import timedelta
from collections import defaultdict

class TrialBalanceCustomHandler(models.AbstractModel):
    _inherit = 'account.trial.balance.report.handler'

    def _custom_line_postprocessor(self, report, options, lines):
        """ Postprocesses the result of the report's _get_lines() before returning it. """
        lines = super()._custom_line_postprocessor(report, options, lines)

        currencies = options.get('currencies', {})
        currency_selected = next((c for c in currencies.values() if c['currency_selected']), None)

        if not currency_selected:
            currency_selected = self.env.company.currency_id
        else:
            currency_selected = self.env['res.currency'].browse(currency_selected['currency_id'])

        for line in lines:
            for column in line.get('columns', []):
                if column.get('figure_type') == 'monetary':
                    column['currency_id'] = currency_selected.id
                    column['currency_symbol'] = currency_selected.symbol
                    value = self.env.company.currency_id._convert(column.get('no_format', 0.0), currency_selected)
                    column['name'] = currency_selected.format(value)

        return lines
