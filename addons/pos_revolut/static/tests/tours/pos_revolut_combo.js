import { registry } from "@web/core/registry";
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";

registry.category("web_tour.tours").add("pos_revolut_combo_extra_checkout", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.clickDisplayedProduct("Quantity combo"),
        {
            content: "The configured extra choice is available in the native combo dialog",
            trigger: ".combo-configurator-popup .revolut-combo-quantity:has(.product-name:contains('Combo first')) .revolut-combo-increase",
            run: "click",
        },
        {
            content: "The maximum selection is enforced and the displayed combo total includes its extra choice",
            trigger: ".combo-configurator-popup .revolut-combo-total:contains('21.00')",
            run() {
                const first = document.querySelector(".combo-configurator-popup .revolut-combo-quantity");
                if (first.querySelector("output").textContent.trim() !== "2" ||
                    !first.querySelector(".revolut-combo-increase").disabled) {
                    throw new Error("The configured maximum of two combo choices was not enforced");
                }
            },
        },
        { trigger: ".combo-configurator-popup .confirm", run: "click" },
        {
            content: "Native displayed totals already include the extra combo selection before authorization",
            trigger: ".product-screen",
            run() {
                if (window.posmodel.get_order().get_total_with_tax() !== 21) {
                    throw new Error("The native cart lost its included and additional combo allocation");
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "21.00"),
        ReceiptScreen.totalAmountContains("21.00"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_combo_native_cash", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.clickDisplayedProduct("Native combo"),
        {
            content: "Ordinary one-choice combos keep their native automatic selection and price",
            trigger: ".product-screen .orderline:contains('Native combo')",
            run() {
                if (document.querySelector(".combo-configurator-popup") ||
                    window.posmodel.get_order().get_total_with_tax() !== 16) {
                    throw new Error("The ordinary native combo changed its selection or price");
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "16.00"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_combo_shared_currency_cash", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.clickDisplayedProduct("Shared currency quantity combo"),
        {
            trigger: ".combo-configurator-popup .revolut-combo-increase",
            run: "click",
        },
        {
            content: "Shared item extras use their loaded source currency before Cash checkout",
            trigger: ".combo-configurator-popup .revolut-combo-total",
            run() {
                const total = document.querySelector(".combo-configurator-popup .revolut-combo-total").textContent;
                if (!total.includes("12.40")) {
                    throw new Error(`Shared-item extras should total 12.40 after currency conversion; received ${total}`);
                }
            },
        },
        { trigger: ".combo-configurator-popup .confirm", run: "click" },
        {
            trigger: ".product-screen .orderline:contains('Shared currency quantity combo')",
            run() {
                if (window.posmodel.get_order().get_total_with_tax() !== 12.4) {
                    throw new Error("The native cart did not preserve converted shared-item extras");
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "12.40"),
        ReceiptScreen.totalAmountContains("12.40"),
    ].flat(),
});

for (const tender of ["Cash", "Revolut"]) {
    registry.category("web_tour.tours").add(`pos_revolut_combo_ordinary_shared_currency_${tender.toLowerCase()}`, {
        steps: () => {
            let originalOrderUuid;
            let prepared = false;
            return [
                Chrome.startPoS(),
                ProductScreen.clickDisplayedProduct("Shared currency ordinary combo"),
                {
                    content: "An ordinary combo keeps native selection and converts its extra before preparation",
                    trigger: ".product-screen .orderline:contains('Shared currency ordinary combo')",
                    run() {
                        const pos = window.posmodel;
                        const order = pos.get_order();
                        const total = order.get_total_with_tax();
                        if (document.querySelector(".combo-configurator-popup") || total !== 11.2) {
                            throw new Error(`Ordinary shared-currency combo should total 11.20 before preparation; received ${total}`);
                        }
                        // Native pricelist recomputation must not restore raw extras or compound FX.
                        order.set_pricelist(order.pricelist_id);
                        order.set_pricelist(order.pricelist_id);
                        if (order.get_total_with_tax() !== 11.2) {
                            throw new Error("Pricelist recomputation lost the ordinary combo currency conversion");
                        }
                        originalOrderUuid = order.uuid;
                        const call = pos.data.call.bind(pos.data);
                        pos.data.call = async (model, method, ...args) => {
                            const result = await call(model, method, ...args);
                            if (model === "pos.order" && method === "revolut_prepare_payment") {
                                if (result.canonical.approval_required || result.canonical.total_minor !== 1120) {
                                    throw new Error("The untouched ordinary combo needs approval or changed its authorized total");
                                }
                                prepared = true;
                            }
                            return result;
                        };
                    },
                },
                ProductScreen.clickPayButton(),
                PaymentScreen.clickPaymentMethod(tender),
                ...(tender === "Cash" ? [PaymentScreen.clickValidate()] : []),
                ReceiptScreen.isShown(),
                ReceiptScreen.paymentLineContains(tender, "11.20"),
                ReceiptScreen.totalAmountContains("11.20"),
                {
                    content: "The corrected amount completes the original native order once",
                    trigger: ".receipt-screen",
                    run() {
                        const order = window.posmodel.get_order();
                        if (order.uuid !== originalOrderUuid || !order.is_paid() ||
                            order.payment_ids.length !== 1 || order.payment_ids[0].amount !== 11.2 ||
                            (tender === "Revolut" && !prepared)) {
                            throw new Error("Ordinary combo checkout lost its identity, tender or server pricing authority");
                        }
                    },
                },
            ].flat();
        },
    });
}

registry.category("web_tour.tours").add("pos_revolut_combo_native_decimal_cash", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.clickDisplayedProduct("Native decimal combo"),
        {
            content: "Ordinary allocation keeps native sequence and decimals instead of rounding each share to the currency quantum",
            trigger: ".product-screen .orderline:contains('Native decimal combo')",
            run() {
                const order = window.posmodel.get_order();
                order.set_pricelist(order.pricelist_id);
                for (const [name, price] of [["Last choice", 0.333], ["First choice", 0.333], ["Middle choice", 0.334]]) {
                    const line = order.lines.find((line) => line.product_id.name === name);
                    if (line?.price_unit !== price) {
                        throw new Error(`Native combo allocation for ${name} should be ${price}; received ${line?.price_unit}`);
                    }
                }
                if (order.get_total_with_tax() !== 1.005) {
                    throw new Error("Native currency rounding no longer agrees with the decimal combo allocation");
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "1.005"),
        ReceiptScreen.totalAmountContains("1.005"),
    ].flat(),
});
