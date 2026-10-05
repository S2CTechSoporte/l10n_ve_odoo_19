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

    @api.model
    def get_secondary_currency_systray(self):
        """Return one reference-currency unit in the active company's currency."""
        company = self.env.company
        company.check_access("read")
        currency = company.secondary_currency_id
        if not currency:
            return False
        amount = currency._convert(
            1.0, company.currency_id, company, fields.Date.context_today(company),
            round=False,
        )
        return {
            "currency_name": currency.name,
            "amount": amount,
            "formatted_amount": formatLang(
                self.env, amount, currency_obj=company.currency_id,
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
