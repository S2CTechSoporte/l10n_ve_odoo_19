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
        currency_name: "EUR",
        amount: 1.12,
        formatted_amount: "$ 1.12",
        can_update: true,
    };
    update = async () => ({ ...data, amount: 1.2, formatted_amount: "$ 1.20" });
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

test("bill icon, bold reference code and conversion; manual update refreshes amount", async () => {
    await mountWithCleanup(SecondaryCurrencyMenu);
    expect(".o_secondary_currency_menu .fa-money").toHaveCount(1);
    expect(".o_secondary_currency_menu .fa-money").toHaveClass("o_secondary_currency_menu_icon");
    expect(".o_secondary_currency_menu strong").toHaveText("EUR");
    expect(".o_secondary_currency_menu button").toHaveText("EUR: $ 1.12");
    await contains(".o_secondary_currency_menu button").click();
    expect(".dropdown-item > i:first-child").toHaveClass(
        "fa-refresh fa-fw o_secondary_currency_menu_icon"
    );
    expect(".dropdown-item > i:first-child").toHaveAttribute("aria-hidden", "true");
    expect(".dropdown-item > span").toHaveText("Update Now");
    expect(".dropdown-item").toHaveText("Update Now");
    await contains(".dropdown-item").click();
    expect(".o_secondary_currency_menu button").toHaveText("EUR: $ 1.20");
    expect(".o_notification").toHaveText("Exchange rates updated.");
});

test("no reference currency hides the navbar item", async () => {
    data = false;
    await mountWithCleanup(SecondaryCurrencyMenu);
    expect(".o_secondary_currency_menu").toHaveCount(0);
});

test("view-only users cannot click the update action", async () => {
    data.can_update = false;
    await mountWithCleanup(SecondaryCurrencyMenu);
    await contains(".o_secondary_currency_menu button").click();
    expect(".dropdown-item").toHaveAttribute("disabled");
});

test("active-company changes and dropdown opening reload the current rate", async () => {
    await mountWithCleanup(SecondaryCurrencyMenu);
    data = { ...data, currency_name: "USD", formatted_amount: "0.80 EUR" };
    userBus.trigger("ACTIVE_COMPANIES_CHANGED");
    await animationFrame();
    expect(".o_secondary_currency_menu strong").toHaveText("USD");
    data = { ...data, formatted_amount: "0.90 EUR" };
    await contains(".o_secondary_currency_menu button").click();
    expect(".o_secondary_currency_menu button").toHaveText("USD: 0.90 EUR");
});

test("errors propagate without a success notification and allow retry", async () => {
    const component = await mountWithCleanup(SecondaryCurrencyMenu);
    update = async () => { throw new Error("Provider unavailable"); };
    await expect(component.updateRates()).rejects.toThrow("Provider unavailable");
    expect(component.state.updating).toBe(false);
    expect(".o_notification").toHaveCount(0);
    expect(".o_secondary_currency_menu button").toHaveText("EUR: $ 1.12");
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
    data = { ...data, currency_name: "USD", formatted_amount: "0.80 EUR" };
    userBus.trigger("ACTIVE_COMPANIES_CHANGED");
    await animationFrame();
    deferred.resolve({ ...data, currency_name: "EUR", formatted_amount: "$ 1.20" });
    await pending;
    await animationFrame();
    expect(".o_secondary_currency_menu strong").toHaveText("USD");
});

test("navbar item is anchored immediately before the company selector", () => {
    const getter = Object.getOwnPropertyDescriptor(NavBar.prototype, "systrayItems").get;
    const keys = getter.call({ env: {} }).map((item) => item.key);
    const companyIndex = keys.indexOf("SwitchCompanyMenu");
    expect(companyIndex).toBeGreaterThan(0);
    expect(keys[companyIndex - 1]).toBe("accounting_dual_currency.SecondaryCurrencyMenu");
});
