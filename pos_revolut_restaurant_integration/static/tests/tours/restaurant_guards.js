import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_restaurant_guards", {
    steps: () => [
        {
            content: "Open Restaurant PoS when the register is closed",
            trigger: ".screen-login .btn.open-register-btn, .floor-screen .floor-map",
            run() {
                if (this.anchor.matches(".screen-login .btn.open-register-btn")) {
                    this.anchor.click();
                }
            },
        },
        { trigger: ".floor-screen .floor-map" },
        {
            content: "A settled Revolut line cannot move into another order",
            trigger: ".floor-screen .floor-map",
            async run() {
                const pos = window.posmodel;
                const method = pos.models["pos.payment.method"].find(
                    (item) => item.use_payment_terminal === "revolut"
                );
                if (!method) {
                    throw new Error("Revolut method was not loaded in Restaurant POS");
                }
                const source = pos.createNewOrder();
                const destination = pos.createNewOrder();
                const payment = source.add_paymentline(method);
                if (!payment) {
                    throw new Error("Could not add a Revolut line to the test order");
                }
                payment.set_payment_status("done");
                const table = pos.models["restaurant.table"].find((item) => item.table_number === 1);
                destination.table_id = table;
                const merged = await pos.transferOrder(source.uuid, table);
                if (merged !== false || !source.get_paymentline_by_uuid(payment.uuid)) {
                    throw new Error("Restaurant merge moved a protected Revolut payment");
                }
                window.revolutRestaurantGuardOrders = { source, destination };
            },
        },
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        {
            content: "A transfer into another order is also guarded",
            trigger: ".floor-screen .floor-map",
            async run() {
                const { source, destination } = window.revolutRestaurantGuardOrders;
                const transferred = await window.posmodel.transferOrder(
                    source.uuid, destination.table_id
                );
                if (transferred !== false || !source.payment_ids.length) {
                    throw new Error("Restaurant transfer moved a protected Revolut payment");
                }
            },
        },
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        {
            content: "Merging into an occupied table is guarded",
            trigger: ".floor-screen .floor-map",
            async run() {
                const pos = window.posmodel;
                const { source, destination } = window.revolutRestaurantGuardOrders;
                const table = pos.models["restaurant.table"].find(
                    (item) => item.table_number === 1
                );
                destination.table_id = table;
                const merged = await pos.transferOrder(source.uuid, table);
                if (merged !== false || !source.payment_ids.length) {
                    throw new Error("Restaurant table merge moved a protected Revolut line");
                }
            },
        },
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        {
            content: "Splitting the exposed order to pay is guarded",
            trigger: ".floor-screen .floor-map",
            async run() {
                const { source } = window.revolutRestaurantGuardOrders;
                const SplitBillScreen = registry.category("pos_screens").get("SplitBillScreen");
                const result = await SplitBillScreen.prototype.createSplittedOrder.call({
                    currentOrder: source,
                    pos: window.posmodel,
                });
                if (result !== false || !source.payment_ids.length) {
                    throw new Error("Restaurant split payment moved a protected Revolut line");
                }
            },
        },
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        {
            content: "Splitting the exposed order to transfer is guarded",
            trigger: ".floor-screen .floor-map",
            async run() {
                const { source } = window.revolutRestaurantGuardOrders;
                const SplitBillScreen = registry.category("pos_screens").get("SplitBillScreen");
                const result = await SplitBillScreen.prototype.createSplittedOrder.call({
                    currentOrder: source,
                    pos: window.posmodel,
                });
                if (result !== false || !source.payment_ids.length) {
                    throw new Error("Restaurant split transfer moved a protected Revolut line");
                }
            },
        },
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        {
            content: "Post-payment tip changes remain guarded in the unified addon",
            trigger: ".floor-screen .floor-map",
            async run() {
                const { source } = window.revolutRestaurantGuardOrders;
                const TipScreen = registry.category("pos_screens").get("TipScreen");
                const result = await TipScreen.prototype.validateTip.call({
                    pos: { get_order: () => source },
                    dialog: window.posmodel.dialog,
                });
                if (result !== false || !source.payment_ids.length) {
                    throw new Error("Restaurant tip adjustment bypassed the Revolut guard");
                }
            },
        },
        { trigger: ".modal:contains('Revolut terminal tip')" },
        Dialog.confirm(),
        {
            content: "An empty-table move keeps the original order and payment",
            trigger: ".floor-screen .floor-map",
            async run() {
                const pos = window.posmodel;
                const { source } = window.revolutRestaurantGuardOrders;
                const table = pos.models["restaurant.table"].find(
                    (item) => item.table_number === 2
                );
                if (!table) {
                    throw new Error("Second Restaurant table was not loaded");
                }
                const uuid = source.uuid;
                const result = await pos.transferOrder(uuid, table);
                if (result === false || source.uuid !== uuid ||
                    source.table_id?.id !== table.id || !source.payment_ids.length) {
                    throw new Error("Restaurant table change lost the original order or payment");
                }
                delete window.revolutRestaurantGuardOrders;
            },
        },
    ],
});
