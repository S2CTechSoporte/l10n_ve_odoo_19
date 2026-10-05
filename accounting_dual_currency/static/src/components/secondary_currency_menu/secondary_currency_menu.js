import { Component, onWillStart, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownGroup } from "@web/core/dropdown/dropdown_group";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { userBus } from "@web/core/user";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

export class SecondaryCurrencyMenu extends Component {
    static template = "accounting_dual_currency.SecondaryCurrencyMenu";
    static components = { Dropdown, DropdownGroup, DropdownItem };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ data: false, updating: false });
        this.loadVersion = 0;
        onWillStart(() => this.loadRate());
        useBus(userBus, "ACTIVE_COMPANIES_CHANGED", () => this.loadRate());
    }

    async loadRate() {
        const version = ++this.loadVersion;
        const data = await this.orm.call("res.company", "get_secondary_currency_systray", []);
        if (version === this.loadVersion) {
            this.state.data = data;
        }
    }

    async updateRates() {
        if (this.state.updating) {
            return;
        }
        this.state.updating = true;
        const version = ++this.loadVersion;
        try {
            const data = await this.orm.call("res.company", "update_secondary_currency_rates", []);
            if (version === this.loadVersion) {
                this.state.data = data;
            }
            this.notification.add(_t("Exchange rates updated."), { type: "success" });
        } finally {
            this.state.updating = false;
        }
    }
}

registry.category("systray").add("accounting_dual_currency.SecondaryCurrencyMenu", {
    Component: SecondaryCurrencyMenu,
}, { sequence: 1 });

// Studio and the company selector share a sequence; anchor to the selector.
patch(NavBar.prototype, {
    get systrayItems() {
        const items = super.systrayItems;
        const index = items.findIndex(
            (item) => item.key === "accounting_dual_currency.SecondaryCurrencyMenu"
        );
        const companyIndex = items.findIndex((item) => item.key === "SwitchCompanyMenu");
        if (index !== -1 && companyIndex !== -1) {
            const [item] = items.splice(index, 1);
            items.splice(items.findIndex((entry) => entry.key === "SwitchCompanyMenu"), 0, item);
        }
        return items;
    },
});
