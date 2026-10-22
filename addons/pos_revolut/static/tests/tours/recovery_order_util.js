import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";

export function reopenRevolutOrder(getOrderUuid) {
    return [
        { trigger: "body:not(:has(.pos-loader))" },
        Chrome.clickMenuOption("Orders"),
        {
            content: "Reopen the original recovery order through the native Orders list",
            trigger: ".ticket-screen .order-row",
            async run(helpers) {
                const order = window.posmodel.models["pos.order"].getBy("uuid", getOrderUuid());
                const rows = [...document.querySelectorAll(".ticket-screen .order-row")].filter((row) =>
                    [...row.querySelectorAll(".col")].some((column) => column.textContent.trim() === order?.pos_reference));
                if (!order || rows.length !== 1) {
                    throw new Error("The original recovery order is missing from the native Orders list");
                }
                await helpers.dblclick(rows[0]);
            },
        },
        {
            content: "Continue the reopened order through its native payment screen",
            trigger: ".product-screen, .payment-screen",
            async run(helpers) {
                if (document.querySelector(".product-screen")) {
                    await helpers.click(".product-screen .pay-order-button");
                }
            },
        },
        {
            trigger: ".payment-screen .paymentline:not(.electronic_payment) .payment-infos:contains('Revolut')",
            run: "click",
        },
    ].flat();
}
