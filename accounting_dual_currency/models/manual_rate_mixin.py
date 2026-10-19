from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import float_compare

MANUAL_RATE_FIELDS = frozenset({"manual_rate", "manual_conversion_rate"})
MANUAL_RATE_GROUPS = ("account.group_account_manager", "base.group_system")


class DualCurrencyManualRateMixin(models.AbstractModel):
    """Manual rate shared by invoices, journal entries, payments and the payment wizard.

    The rate is captured with the orientation of ``conversion_rate_display`` (e.g.
    880.0 bolivars per dollar whichever of the two currencies is the USD) and applies
    to the conversions between the company and the reference currency.

    Only accounting administrators and settings administrators may capture or change
    it. A document can carry the rate of its source document (the entry of a payment
    carries the rate of the payment, a reversal that of the entry it reverses).
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not MANUAL_RATE_FIELDS.isdisjoint(vals):
                self._check_manual_rate_access(vals)
        return super().create(vals_list)

    def write(self, vals):
        if not MANUAL_RATE_FIELDS.isdisjoint(vals):
            for record in self:
                record._check_manual_rate_access(vals)
        return super().write(vals)

    def _can_set_manual_rate(self):
        """Whether the current user may capture or change a manual rate."""
        return self.env.su or any(
            self.env.user.has_group(group) for group in MANUAL_RATE_GROUPS
        )

    def _get_inherited_manual_rate_vals(self, vals):
        """Return the manual rate values this record carries from its source document.

        The rate of a source document was already captured by someone allowed to, so
        carrying it does not require the right to set a manual rate. Return None when
        the record has no source document.
        """
        return None

    @staticmethod
    def _get_manual_rate_state(manual_rate, manual_conversion_rate):
        """Return the effective (enabled, rate) pair: the rate only counts when enabled."""
        return (True, manual_conversion_rate) if manual_rate else (False, 0.0)

    def _check_manual_rate_access(self, vals):
        """Reject a manual rate captured by a user who is not allowed to set it."""
        if self._can_set_manual_rate():
            return
        current = self._get_manual_rate_state(
            self.manual_rate, self.manual_conversion_rate
        )
        requested = self._get_manual_rate_state(
            vals.get("manual_rate", self.manual_rate),
            vals.get("manual_conversion_rate", self.manual_conversion_rate),
        )
        if self._is_same_manual_rate(requested, current):
            return
        inherited = self._get_inherited_manual_rate_vals(vals)
        if inherited is not None and self._is_same_manual_rate(
            requested,
            self._get_manual_rate_state(
                inherited["manual_rate"], inherited["manual_conversion_rate"]
            ),
        ):
            return
        raise AccessError(
            _(
                "Only accounting administrators and settings administrators can "
                "set or change the manual rate."
            )
        )

    @staticmethod
    def _is_same_manual_rate(state, other_state):
        return state[0] == other_state[0] and not float_compare(
            state[1], other_state[1], precision_digits=8
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
