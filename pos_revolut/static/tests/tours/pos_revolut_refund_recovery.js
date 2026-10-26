import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const RECOVERY_KEY = "revolut-manager-refund-recovery";

function recoveryIdentity(order) {
    return {
        uuid: order.uuid, id: order.id,
        payments: order.payment_ids.map((line) => ({
            id: line.id, uuid: line.uuid, transaction: line.transaction_id,
            reference: line.payment_ref_no, amount: line.amount,
        })),
    };
}

function resumeSteps({ split = false } = {}) {
    return [
        {
            trigger: ".o_form_view button[name='action_check_status']",
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: ".o_form_view button[name='action_recover_return']",
            run: "click",
            expectUnloadPage: true,
        },
        PaymentScreen.isShown(),
        // Native Odoo 19 only displays electronic status for the selected
        // tender, and labels completed refunds "Payment Successful" too.
        { trigger: ".payment-screen .paymentline .payment-infos:contains('Revolut')", run: "click" },
        {
            trigger: ".payment-screen .electronic_status:contains('Payment Successful')",
            run() {
                const order = window.posmodel.getOrder();
                if (window.location.pathname !== `/pos/ui/${order.config_id.id}/payment/${order.uuid}` ||
                        !Number.isInteger(order.id) || order.state !== "draft" ||
                        order.payment_ids.length !== 1 || !order.payment_ids[0].isDone()) {
                    throw new Error("Manager recovery did not open the saved return through native Odoo 19 routing");
                }
                sessionStorage.setItem(RECOVERY_KEY, JSON.stringify(recoveryIdentity(order)));
            },
        },
        refresh(),
        { trigger: ".payment-screen .paymentline .payment-infos:contains('Revolut')", run: "click" },
        {
            trigger: ".payment-screen .electronic_status:contains('Payment Successful')",
            run() {
                const order = window.posmodel.getOrder();
                const before = JSON.parse(sessionStorage.getItem(RECOVERY_KEY));
                if (JSON.stringify(recoveryIdentity(order)) !== JSON.stringify(before) ||
                        !order.payment_ids[0].isDone() || order.state !== "draft") {
                    throw new Error("Reload replaced the saved return, tender or verified references");
                }
            },
        },
        ...(split ? [
            {
                trigger: ".payment-screen",
                run() {
                    const order = window.posmodel.getOrder();
                    if (order.remainingDue !== -6.17 || order.payment_ids.length !== 1 ||
                            order.payment_ids[0].payment_method_id.is_cash_count) {
                        throw new Error("Recovered card refund must leave its manual Cash share outstanding");
                    }
                },
            },
            PaymentScreen.clickPaymentMethod("Cash"),
        ] : []),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.totalAmountContains("-12.34"),
        ReceiptScreen.paymentLineContains("Revolut", split ? "-6.17" : "-12.34"),
        ...(split ? [ReceiptScreen.paymentLineContains("Cash", "-6.17")] : []),
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_manager_resume_waiting", {
    steps: () => resumeSteps(),
});
registry.category("web_tour.tours").add("pos_revolut_manager_resume_mixed", {
    steps: () => resumeSteps({ split: true }),
});
