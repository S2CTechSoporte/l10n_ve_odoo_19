import { AgedPartnerBalanceFilters } from "@account_reports/components/aged_partner_balance/filters";
import { patch } from "@web/core/utils/patch";

patch(AgedPartnerBalanceFilters.prototype, {
    async selectDualCurrency(currencyId) {
        await this.filterClicked({
            optionKey: "dual_currency_id",
            optionValue: currencyId,
            reload: true,
        });
    },
});
