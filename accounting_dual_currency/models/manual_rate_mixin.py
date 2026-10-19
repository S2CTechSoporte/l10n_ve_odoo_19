from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DualCurrencyManualRateMixin(models.AbstractModel):
    """Manual rate shared by invoices, payments and the register payment wizard.

    The rate is captured with the orientation of ``conversion_rate_display`` (e.g.
    880.0 bolivars per dollar whichever of the two currencies is the USD) and applies
    to the conversions between the company and the reference currency.
    """

    _name = "dual.currency.manual.rate.mixin"
    _description = "Dual Currency Manual Rate Mixin"

    manual_rate = fields.Boolean(
        string="Manual Rate",
        copy=False,
        help="Convert the company and reference currency amounts with the manual rate "
        "of this document instead of the exchange rates of Odoo.",
    )
    manual_conversion_rate = fields.Float(
        string="Manual Rate Value",
        copy=False,
        digits=0,
        help="Manual rate with the orientation of the USD Rate indicator: the value of "
        "one dollar in the other currency of the pair, e.g. 880.0 bolivars per dollar "
        "whichever the company currency is. Without USD in the pair it is the number "
        "of company currency units per reference currency unit.",
    )
    manual_rate_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Manual Rate Currency",
        compute="_compute_manual_rate_display",
    )
    manual_rate_is_usd = fields.Boolean(
        string="Manual Rate Uses USD",
        compute="_compute_manual_rate_display",
    )
    manual_rate_available = fields.Boolean(
        string="Manual Rate Available",
        compute="_compute_manual_rate_available",
    )
    manual_rate_active = fields.Boolean(
        string="Manual Rate In Use",
        compute="_compute_manual_rate_active",
    )

    def _get_manual_rate_company(self):
        return self.company_id

    def _get_manual_rate_currency(self):
        return self.currency_id

    def _get_manual_rate_date(self):
        return fields.Date.context_today(self)

    def _is_manual_rate_document(self):
        """Whether this kind of record converts its amounts with a rate it can own."""
        return True

    @api.depends("company_id.currency_id", "company_id.secondary_currency_id")
    def _compute_manual_rate_display(self):
        for record in self:
            company = record._get_manual_rate_company()
            if not (company and company.secondary_currency_id):
                record.manual_rate_currency_id = False
                record.manual_rate_is_usd = False
                continue
            display = company._get_conversion_rate_display(1.0)
            record.manual_rate_currency_id = display[
                "conversion_rate_display_currency_id"
            ]
            record.manual_rate_is_usd = display["conversion_rate_display_is_usd"]

    @api.depends(
        "currency_id",
        "company_id.currency_id",
        "company_id.secondary_currency_id",
    )
    def _compute_manual_rate_available(self):
        for record in self:
            company = record._get_manual_rate_company()
            reference_currency = company.secondary_currency_id
            record.manual_rate_available = bool(
                company
                and reference_currency
                and reference_currency != company.currency_id
                and record._get_manual_rate_currency()
                in (company.currency_id | reference_currency)
                and record._is_manual_rate_document()
            )

    @api.depends("manual_rate", "manual_conversion_rate", "manual_rate_available")
    def _compute_manual_rate_active(self):
        for record in self:
            record.manual_rate_active = bool(
                record.manual_rate
                and record.manual_rate_available
                and record.manual_conversion_rate > 0
            )

    @api.constrains("manual_rate", "manual_conversion_rate", "currency_id")
    def _check_manual_rate(self):
        for record in self.filtered("manual_rate"):
            if not record.manual_rate_available:
                raise ValidationError(
                    _(
                        "The manual rate is only available when the company has a "
                        "reference currency and the document uses the company "
                        "currency or the reference currency."
                    )
                )
            if record.manual_conversion_rate <= 0:
                raise ValidationError(_("The manual rate must be strictly positive."))

    @api.onchange("manual_rate")
    def _onchange_manual_rate(self):
        for record in self:
            if record.manual_rate and not record.manual_conversion_rate:
                record.manual_conversion_rate = (
                    record._get_system_manual_conversion_rate()
                )

    @api.onchange("currency_id", "company_id")
    def _onchange_manual_rate_availability(self):
        for record in self:
            if record.manual_rate and not record.manual_rate_available:
                record.manual_rate = False

    def _get_system_manual_conversion_rate(self):
        """Return the rate of Odoo with the orientation of the manual rate."""
        self.ensure_one()
        company = self._get_manual_rate_company()
        reference_currency = company.secondary_currency_id
        if not (company and reference_currency) or (
            reference_currency == company.currency_id
        ):
            return 0.0
        rate = self.env["res.currency"].with_context(
            manual_rate=False, dual_currency_manual_rate=False
        )._get_conversion_rate(
            from_currency=company.currency_id,
            to_currency=reference_currency,
            company=company,
            date=self._get_manual_rate_date(),
        )
        if not rate:
            return 0.0
        display = company._get_conversion_rate_display(1.0 / rate)
        return display["conversion_rate_display"]

    def _get_manual_rate_spec(self):
        """Return the ``dual_currency_manual_rate`` context value, or None."""
        self.ensure_one()
        if not (
            self.manual_rate
            and self.manual_rate_available
            and self.manual_conversion_rate > 0
        ):
            return None
        return self._get_manual_rate_company()._get_manual_rate_spec(
            self.manual_conversion_rate
        )

    def _get_manual_rate_context(self):
        """Context applying the manual rate, or clearing any inherited one."""
        self.ensure_one()
        return {"dual_currency_manual_rate": self._get_manual_rate_spec() or False}

    def _with_manual_rate(self):
        """Return the record in the context of its manual rate (itself when it has none)."""
        self.ensure_one()
        manual_context = self._get_manual_rate_context()
        if (
            not manual_context["dual_currency_manual_rate"]
            and not self.env.context.get("dual_currency_manual_rate")
        ):
            return self
        return self.with_context(**manual_context)

    def _get_dual_currency_conversion_context(self):
        """Context of the dual currency conversions: no foreign rate, own manual rate."""
        self.ensure_one()
        return {"manual_rate": False, **self._get_manual_rate_context()}
