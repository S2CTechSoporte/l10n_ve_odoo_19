import math
import re
from datetime import datetime

import requests
from lxml import etree, html

from odoo import api, fields, models
from odoo.exceptions import UserError


BCV_URL = "https://www.bcv.org.ve/"
BCV_CURRENCY_BLOCKS = {
    "USD": "dolar",
    "EUR": "euro",
    "CNY": "yuan",
    "TRY": "lira",
    "RUB": "rublo",
}
BOLIVAR_CODES = {"VES", "VEF"}


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_provider = fields.Selection(
        selection_add=[("bcv", "[VE] Central Bank of Venezuela (BCV)")],
        ondelete={"bcv": "set null"},
    )

    @api.model
    def _parse_bcv_data(self, available_currencies):
        """Return USD-based quotations for the native currency-rate updater.

        VEF is a compatibility alias for the current VES quotation, not a
        historical redenomination conversion. Only active bolivar currencies
        and the foreign company currencies needed for normalization are returned.
        """
        currency_codes = set(available_currencies.mapped("name"))
        bolivar_codes = currency_codes & BOLIVAR_CODES
        if "USD" not in currency_codes or not bolivar_codes:
            raise UserError(
                self.env._(
                    "The BCV provider requires USD and at least one of VES or VEF "
                    "to be active."
                )
            )

        company_codes = set(self.mapped("currency_id.name"))
        unsupported_codes = company_codes - (BCV_CURRENCY_BLOCKS.keys() | BOLIVAR_CODES)
        if unsupported_codes:
            raise UserError(
                self.env._(
                    "The BCV does not publish quotations for the following company "
                    "currencies: %(currencies)s.",
                    currencies=", ".join(sorted(unsupported_codes)),
                )
            )
        inactive_codes = company_codes - currency_codes
        if inactive_codes:
            raise UserError(
                self.env._(
                    "The BCV provider requires these company currencies to be active: "
                    "%(currencies)s.",
                    currencies=", ".join(sorted(inactive_codes)),
                )
            )

        try:
            # Temporary opt-out for BCV's incomplete certificate chain.
            response = requests.get(BCV_URL, timeout=20, verify=False)
            response.raise_for_status()
        except requests.RequestException as error:
            raise UserError(
                self.env._(
                    "Could not retrieve the official BCV exchange rate: %(error)s",
                    error=str(error),
                )
            ) from error

        rate, value_date = self._extract_bcv_rate(response.content)
        rates = {code: (rate, value_date) for code in sorted(bolivar_codes)}
        rates["USD"] = (1.0, value_date)
        for code in sorted(company_codes - BOLIVAR_CODES - {"USD"}):
            quotation, quotation_date = self._extract_bcv_rate(
                response.content, currency_code=code
            )
            if quotation_date != value_date:
                raise UserError(
                    self.env._(
                        "The BCV quotations must share the same official value date."
                    )
                )
            cross_rate = rate / quotation
            if not math.isfinite(cross_rate) or cross_rate <= 0:
                raise UserError(
                    self.env._(
                        "The BCV %(currency)s quotation cannot be represented as a "
                        "positive finite cross-rate.",
                        currency=code,
                    )
                )
            rates[code] = (cross_rate, value_date)
        return rates

    def _generate_currency_rates(self, parsed_data):
        """Restrict BCV destinations while keeping native rate normalization.

        Foreign companies update bolivars; bolivar companies update USD.
        Company currencies and bolivar aliases retain their unit reference
        records. Other providers receive their original, unfiltered data.
        """
        other_companies = self.filtered(lambda company: company.currency_provider != "bcv")
        if other_companies:
            super(ResCompany, other_companies)._generate_currency_rates(parsed_data)
        for company in self - other_companies:
            currency_codes = BOLIVAR_CODES | {company.currency_id.name}
            if company.currency_id.name in BOLIVAR_CODES:
                currency_codes.add("USD")
            company_data = {
                code: rate_info
                for code, rate_info in parsed_data.items()
                if code in currency_codes
            }
            super(ResCompany, company)._generate_currency_rates(company_data)

    @api.model
    def _extract_bcv_rate(self, content, currency_code="USD"):
        """Extract a bolivars-per-currency quotation and its official value date.

        The date must belong to the same rates block as the requested currency.
        Missing, ambiguous or invalid data is rejected before rates are written.
        """
        block_id = BCV_CURRENCY_BLOCKS.get(currency_code)
        if not block_id:
            raise UserError(
                self.env._(
                    "The BCV does not publish a quotation for %(currency)s.",
                    currency=currency_code,
                )
            )
        try:
            document = html.fromstring(content)
        except etree.ParserError as error:
            raise UserError(
                self.env._("The BCV response does not contain a valid HTML page.")
            ) from error

        currency_blocks = document.xpath("//div[@id=$block_id]", block_id=block_id)
        if len(currency_blocks) != 1:
            raise UserError(
                self.env._(
                    "The BCV page must contain exactly one %(currency)s rates block.",
                    currency=currency_code,
                )
            )

        rate_nodes = currency_blocks[0].xpath(".//strong")
        if len(rate_nodes) != 1:
            raise UserError(
                self.env._(
                    "The BCV %(currency)s rates block must contain exactly one quotation.",
                    currency=currency_code,
                )
            )

        rate_text = "".join(rate_nodes[0].itertext()).strip()
        if not re.fullmatch(
            r"(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+),[0-9]+", rate_text
        ):
            raise UserError(
                self.env._(
                    "The BCV %(currency)s quotation is not a valid Spanish-format number.",
                    currency=currency_code,
                )
            )
        rate = float(rate_text.replace(".", "").replace(",", "."))
        if not math.isfinite(rate) or rate <= 0:
            raise UserError(
                self.env._(
                    "The BCV %(currency)s quotation must be finite and strictly positive.",
                    currency=currency_code,
                )
            )

        value_dates = currency_blocks[0].xpath(
            "ancestor::div[contains(concat(' ', normalize-space(@class), ' '),"
            " ' views-row ')][1]"
            "//span[contains(concat(' ', normalize-space(@class), ' '),"
            " ' date-display-single ')]/@content"
        )
        if len(value_dates) != 1:
            raise UserError(
                self.env._(
                    "The BCV rates block must contain exactly one official value date."
                )
            )
        try:
            value_date = datetime.fromisoformat(value_dates[0]).date()
        except ValueError as error:
            raise UserError(
                self.env._("The BCV official value date is not a valid ISO date.")
            ) from error

        return rate, value_date
