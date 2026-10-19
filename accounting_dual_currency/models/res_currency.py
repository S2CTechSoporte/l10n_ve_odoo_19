from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _get_conversion_rate(self, from_currency, to_currency, company=None, date=None):
        """Apply the manual rate of a document to its company/reference currency pair.

        The rate travels in the ``dual_currency_manual_rate`` context key as the tuple
        ``(root_company_id, company_currency_id, reference_currency_id, rate)``, where
        ``rate`` is expressed in company-currency units per reference-currency unit.
        Any other currency pair, any other company and any call without the key keep
        the standard Odoo rate lookup.
        """
        manual_rate = self._get_dual_currency_manual_rate(
            from_currency, to_currency, company
        )
        if manual_rate:
            return manual_rate
        return super()._get_conversion_rate(
            from_currency, to_currency, company=company, date=date
        )

    @api.model
    def _get_dual_currency_manual_rate(self, from_currency, to_currency, company=None):
        """Return the manual rate from ``from_currency`` to ``to_currency``, or 0."""
        manual_rate = self.env.context.get("dual_currency_manual_rate")
        if not manual_rate or from_currency == to_currency:
            return 0.0
        root_company_id, company_currency_id, reference_currency_id, rate = manual_rate
        if (company or self.env.company).root_id.id != root_company_id:
            return 0.0
        if (
            from_currency.id == company_currency_id
            and to_currency.id == reference_currency_id
        ):
            return 1.0 / rate
        if (
            from_currency.id == reference_currency_id
            and to_currency.id == company_currency_id
        ):
            return rate
        return 0.0
