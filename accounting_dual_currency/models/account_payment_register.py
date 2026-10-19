from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _name = "account.payment.register"
    _inherit = ["account.payment.register", "dual.currency.manual.rate.mixin"]

    def _get_manual_rate_date(self):
        return self.payment_date or fields.Date.context_today(self)

    def _is_manual_rate_document(self):
        """The rate belongs to the single payment created from an editable wizard."""
        return bool(
            self.can_edit_wizard and (not self.can_group_payments or self.group_payment)
        )

    @api.depends("can_edit_wizard", "can_group_payments", "group_payment")
    def _compute_manual_rate_available(self):
        super()._compute_manual_rate_available()

    @api.depends("manual_rate", "manual_conversion_rate")
    def _compute_amount(self):
        super()._compute_amount()

    @api.depends("manual_rate", "manual_conversion_rate")
    def _compute_payment_difference(self):
        super()._compute_payment_difference()

    def _get_total_amounts_to_pay(self, batch_results):
        """Convert the amounts to pay at the manual rate of the wizard, when it has one.

        The journal items convert their amounts through their own currency, so the
        manual rate is bound to the lines of the batches as well.
        """
        self.ensure_one()
        manual_context = self._get_manual_rate_context()
        if (
            not manual_context["dual_currency_manual_rate"]
            and not self.env.context.get("dual_currency_manual_rate")
        ):
            return super()._get_total_amounts_to_pay(batch_results)
        batch_results = [
            {
                **batch_result,
                "lines": batch_result["lines"].with_context(**manual_context),
            }
            for batch_result in batch_results
        ]
        return super(
            AccountPaymentRegister, self.with_context(**manual_context)
        )._get_total_amounts_to_pay(batch_results)

    @api.onchange("currency_id")
    def _onchange_currency_id(self):
        return super(AccountPaymentRegister, self._with_manual_rate())._onchange_currency_id()

    def _get_manual_rate_payment_vals(self):
        """Return the manual rate values of the payment created by the wizard."""
        self.ensure_one()
        if self._get_manual_rate_spec():
            return {
                "manual_rate": True,
                "manual_conversion_rate": self.manual_conversion_rate,
            }
        return {}

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super(
            AccountPaymentRegister, self._with_manual_rate()
        )._create_payment_vals_from_wizard(batch_result)
        payment_vals.update(self._get_manual_rate_payment_vals())
        return payment_vals
