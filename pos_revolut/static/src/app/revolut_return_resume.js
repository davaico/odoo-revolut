import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

// Odoo 18 has no payment/<uuid> route. Manager actions open the native
// register, then select its already-saved return after shared drafts load.
patch(PosStore.prototype, {
    async postSyncAllOrders(orders) {
        const result = await super.postSyncAllOrders(...arguments);
        const url = new URL(window.location.href);
        const uuid = url.searchParams.get("revolut_return_uuid");
        // Keep unfinished returns resumable across reloads. Consume only the
        // navigation for this return after native synchronization confirms it.
        if (uuid && orders.some((order) => order.uuid === uuid &&
                order.session_id?.id === this.session.id &&
                ["paid", "done", "invoiced"].includes(order.state))) {
            url.searchParams.delete("revolut_return_uuid");
            window.history.replaceState(window.history.state, "", url);
        }
        return result;
    },

    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        this.revolutReturnResumeReady = true;
        this._resumeRevolutManagerReturn();
        return result;
    },

    showScreen(name, props) {
        const result = super.showScreen(...arguments);
        if (name === "ProductScreen" && this.revolutReturnResumeReady) {
            this._resumeRevolutManagerReturn();
        }
        return result;
    },

    _resumeRevolutManagerReturn() {
        // Preserve native employee login. A register may select its cashier
        // only after the shared data finished loading.
        if (!this.cashier || this.revolutReturnResumeHandled) {
            return;
        }
        const uuid = new URLSearchParams(window.location.search).get("revolut_return_uuid");
        if (!uuid) {
            return;
        }
        this.revolutReturnResumeHandled = true;
        const order = this.models["pos.order"].getBy("uuid", uuid);
        const refundLine = order?.payment_ids.find((line) =>
            line.amount < 0 && line.uiState.revolutSnapshot?.operation_id);
        if (!order || order.state !== "draft" || order.session_id?.id !== this.session.id || !refundLine) {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut return unavailable"),
                body: _t("Reopen the refund worklist and review its linked return and session before continuing."),
            });
            return;
        }
        this.set_order(order);
        order.select_paymentline(refundLine);
        this.showScreen("PaymentScreen", { orderUuid: order.uuid });
    },
});
