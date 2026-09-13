/** @odoo-module **/

import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AgedPartnerBalanceFilters } from "@account_reports/components/aged_partner_balance/filters";


export class S2CSalespersonStateAgedPartnerBalanceFilters extends AgedPartnerBalanceFilters {
    static template = "s2c_salesperson_state.AgedPartnerBalanceFilters";
}

AccountReport.registerCustomComponent(S2CSalespersonStateAgedPartnerBalanceFilters);