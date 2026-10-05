import { beforeEach, expect, test } from "@odoo/hoot";
import { Deferred, animationFrame } from "@odoo/hoot-mock";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import {
    contains, mockService, mountWithCleanup,
} from "@web/../tests/web_test_helpers";
import { userBus } from "@web/core/user";
import { NavBar } from "@web/webclient/navbar/navbar";
import { SecondaryCurrencyMenu } from "@accounting_dual_currency/components/secondary_currency_menu/secondary_currency_menu";

defineMailModels();

let data;
let update;

beforeEach(() => {
    data = {
        currency_name: "USD",
        amount: 1 / 1.12,
        formatted_amount: "0,89\u00a0\u20ac",
        can_update: true,
    };
    update = async () => ({ ...data, amount: 1 / 1.2, formatted_amount: "0,83\u00a0\u20ac" });
    mockService("orm", {
        async call(model, method, args) {
            expect(model).toBe("res.company");
            expect(args).toEqual([]);
            if (method === "update_secondary_currency_rates") {
                return update();
            }
            expect(method).toBe("get_secondary_currency_systray");
            return data;
        },
    });
});

test("bill icon, bold USD code and localized quotation; manual update refreshes amount", async () => {
    await mountWithCleanup(SecondaryCurrencyMenu);
    expect(".o_secondary_currency_menu .fa-money").toHaveCount(1);
    expect(".o_secondary_currency_menu .fa-money").toHaveClass("o_secondary_currency_menu_icon");
    expect(".o_secondary_currency_menu strong").toHaveText("USD");
    expect(".o_secondary_currency_menu button").toHaveText("USD: 0,89 \u20ac");
    expect(".o_secondary_currency_menu button > span").toHaveStyle({ marginLeft: "0px" });
    await contains(".o_secondary_currency_menu button").click();
    expect(".dropdown-item > i:first-child").toHaveClass(
        "fa-refresh fa-fw o_secondary_currency_menu_icon"
    );
    expect(".dropdown-item > i:first-child").toHaveAttribute("aria-hidden", "true");
    expect(".dropdown-item > span").toHaveText("Update Now");
    expect(".dropdown-item").toHaveText("Update Now");
    await contains(".dropdown-item").click();
    expect(".o_secondary_currency_menu button").toHaveText("USD: 0,83 \u20ac");
    expect(".o_notification").toHaveText("Exchange rates updated.");
});

test("counterpart currency symbol before the amount is preserved", async () => {
    data.formatted_amount = "\u20ac\u00a00,89";
    await mountWithCleanup(SecondaryCurrencyMenu);
    expect(".o_secondary_currency_menu strong").toHaveText("USD");
    expect(".o_secondary_currency_menu button").toHaveText("USD: \u20ac 0,89");
});

test("no reference currency hides the navbar item", async () => {
    data = false;
    await mountWithCleanup(SecondaryCurrencyMenu);
    expect(".o_secondary_currency_menu").toHaveCount(0);
});

test("company changes hide and restore the USD quotation", async () => {
    await mountWithCleanup(SecondaryCurrencyMenu);
    const quotation = data;
    data = false;
    userBus.trigger("ACTIVE_COMPANIES_CHANGED");
    await animationFrame();
    expect(".o_secondary_currency_menu").toHaveCount(0);
    data = quotation;
    userBus.trigger("ACTIVE_COMPANIES_CHANGED");
    await animationFrame();
    expect(".o_secondary_currency_menu strong").toHaveText("USD");
    expect(".o_secondary_currency_menu button").toHaveText("USD: 0,89 \u20ac");
});

test("view-only users cannot click the update action", async () => {
    data.can_update = false;
    await mountWithCleanup(SecondaryCurrencyMenu);
    await contains(".o_secondary_currency_menu button").click();
    expect(".dropdown-item").toHaveAttribute("disabled");
});

test("active-company changes and dropdown opening reload the current rate", async () => {
    await mountWithCleanup(SecondaryCurrencyMenu);
    data = { ...data, amount: 0.8, formatted_amount: "\u00a3 0,80" };
    userBus.trigger("ACTIVE_COMPANIES_CHANGED");
    await animationFrame();
    expect(".o_secondary_currency_menu strong").toHaveText("USD");
    expect(".o_secondary_currency_menu button").toHaveText("USD: \u00a3 0,80");
    data = { ...data, amount: 0.9, formatted_amount: "\u00a3 0,90" };
    await contains(".o_secondary_currency_menu button").click();
    expect(".o_secondary_currency_menu button").toHaveText("USD: \u00a3 0,90");
});

test("errors propagate without a success notification and allow retry", async () => {
    const component = await mountWithCleanup(SecondaryCurrencyMenu);
    update = async () => { throw new Error("Provider unavailable"); };
    await expect(component.updateRates()).rejects.toThrow("Provider unavailable");
    expect(component.state.updating).toBe(false);
    expect(".o_notification").toHaveCount(0);
    expect(".o_secondary_currency_menu button").toHaveText("USD: 0,89 \u20ac");
    update = async () => ({ ...data, amount: 1 / 1.2, formatted_amount: "0,83\u00a0\u20ac" });
    await component.updateRates();
    await animationFrame();
    expect(component.state.updating).toBe(false);
    expect(".o_secondary_currency_menu button").toHaveText("USD: 0,83 \u20ac");
    expect(".o_notification").toHaveText("Exchange rates updated.");
});

test("duplicate updates are blocked; an old response cannot overwrite the new company", async () => {
    const component = await mountWithCleanup(SecondaryCurrencyMenu);
    const deferred = new Deferred();
    let calls = 0;
    update = () => {
        calls++;
        return deferred;
    };
    const pending = component.updateRates();
    await component.updateRates();
    expect(calls).toBe(1);
    data = { ...data, amount: 0.8, formatted_amount: "\u00a3 0,80" };
    userBus.trigger("ACTIVE_COMPANIES_CHANGED");
    await animationFrame();
    deferred.resolve({ ...data, amount: 1 / 1.2, formatted_amount: "0,83\u00a0\u20ac" });
    await pending;
    await animationFrame();
    expect(".o_secondary_currency_menu strong").toHaveText("USD");
    expect(".o_secondary_currency_menu button").toHaveText("USD: \u00a3 0,80");
});

test("navbar item is anchored immediately before the company selector", () => {
    const getter = Object.getOwnPropertyDescriptor(NavBar.prototype, "systrayItems").get;
    const keys = getter.call({ env: {} }).map((item) => item.key);
    const companyIndex = keys.indexOf("SwitchCompanyMenu");
    expect(companyIndex).toBeGreaterThan(0);
    expect(keys[companyIndex - 1]).toBe("accounting_dual_currency.SecondaryCurrencyMenu");
});
