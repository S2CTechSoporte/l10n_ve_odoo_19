import { expect, test } from "@odoo/hoot";
import { animationFrame, click } from "@odoo/hoot-dom";

import { TierReviewMenu } from "@base_tier_validation/components/tier_review_menu/tier_review_menu";
import { mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";

test.tags("desktop");

test("TierReviewMenu uses the Odoo 19 Dropdown API", async () => {
    mockService("orm", {
        async call(model, method) {
            expect.step(`${model}.${method}`);
            return [
                {
                    model: "tier.validation.tester",
                    name: "Tier Validation",
                    icon: "/mail/static/img/smiley/avatar.jpg",
                    pending_count: 2,
                },
            ];
        },
    });
    mockService("action", {
        doAction(action) {
            expect.step(`doAction:${action.res_model}`);
        },
    });
    mockService("mail.store", {
        tierReviewCounter: 0,
        tierReviewGroups: [],
    });

    await mountWithCleanup(TierReviewMenu);
    await animationFrame();

    expect(".o-mail-ActivityMenu-counter").toHaveText("2");
    await click(".o-mail-DiscussSystray-class button");
    await animationFrame();
    expect(".o-mail-ActivityGroup").toHaveCount(1);
    await click(".o-mail-ActivityGroup");
    expect.verifySteps([
        "res.users.review_user_count",
        "res.users.review_user_count",
        "doAction:tier.validation.tester",
    ]);
});