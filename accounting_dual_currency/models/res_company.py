from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import formatLang


class ResCompany(models.Model):
    _inherit = "res.company"

    secondary_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Reference Currency",
        default=lambda self: self._get_secondary_currency_id(),
        help="Secondary currency used to display accounting amounts.",
    )

    def _get_secondary_currency_id(self):
        usd = self.env.ref("base.USD")
        return usd if self.env.company.currency_id != usd else False

    def _get_conversion_rate_display(self, conversion_rate):
        """Orient a stored company/reference rate without looking up rates or dates."""
        self.ensure_one()
        usd = self.env.ref("base.USD")
        company_currency = self.currency_id
        reference_currency = self.secondary_currency_id
        is_usd = bool(reference_currency and usd in (company_currency, reference_currency))
        currency = company_currency
        if is_usd and company_currency == usd and reference_currency != usd:
            if conversion_rate <= 0:
                raise UserError(_("The stored conversion rate must be positive to display a USD quotation."))
            conversion_rate = 1.0 / conversion_rate
            currency = reference_currency
        return {
            "conversion_rate_display_currency_id": currency.id,
            "conversion_rate_display_is_usd": is_usd,
            "conversion_rate_display": conversion_rate,
        }

    @api.model
    def get_secondary_currency_systray(self):
        """Return one USD in the active company's counterpart currency."""
        company = self.env.company
        company.check_access("read")
        currency = company.secondary_currency_id
        if not currency:
            return False
        usd = self.env.ref("base.USD")
        if company.currency_id != usd:
            currency = company.currency_id
        amount = usd._convert(
            1.0, currency, company, fields.Date.context_today(company),
            round=False,
        )
        return {
            "currency_name": usd.name,
            "amount": amount,
            "formatted_amount": formatLang(
                self.env, amount, currency_obj=currency,
            ),
            "can_update": self.env.user.has_group("base.group_system")
            or self.env.user.has_group("account.group_account_manager"),
        }

    @api.model
    def update_secondary_currency_rates(self):
        """Authorize a scoped call to Odoo's standard manual rate updater."""
        if not (
            self.env.user.has_group("base.group_system")
            or self.env.user.has_group("account.group_account_manager")
        ):
            raise AccessError(_(
                "Only Settings administrators and Accounting managers can update exchange rates."
            ))
        company = self.env.company
        company.check_access("read")
        rate_company = company.root_id
        rate_company.check_access("read")
        if not rate_company.currency_provider:
            raise UserError(_("Configure an exchange rate provider in Accounting settings first."))
        # Elevate only the transient settings call, after group and company checks.
        settings = self.env["res.config.settings"].sudo().create({
            "company_id": rate_company.id,
        })
        settings.with_context(suppress_errors=False).update_currency_rates_manually()
        return self.get_secondary_currency_systray()
