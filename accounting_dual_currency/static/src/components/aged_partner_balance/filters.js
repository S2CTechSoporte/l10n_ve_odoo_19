import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { patch } from "@web/core/utils/patch";

patch(AccountReportFilters.prototype, {
    async selectDualCurrency(currencyId) {
        await this.filterClicked({
            optionKey: "dual_currency_id",
            optionValue: currencyId,
            reload: true,
        });
    },
});
