import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { SplitBillScreen } from "@pos_restaurant/app/screens/split_bill_screen/split_bill_screen";
import { hasRevolutExposure } from "@pos_revolut/app/payment_revolut";

function explainGuard(dialog) {
    dialog.add(AlertDialog, {
        title: _t("Revolut payment attached to this order"),
        body: _t("Check or reconcile the Revolut payment before splitting or merging this order. A table change that keeps the same order is allowed."),
    });
}

patch(PosStore.prototype, {
    async mergeOrders(sourceOrder, destinationOrder) {
        if (hasRevolutExposure(sourceOrder) || hasRevolutExposure(destinationOrder)) {
            explainGuard(this.dialog);
            return false;
        }
        return super.mergeOrders(...arguments);
    },

    async transferOrder(orderUuid, destinationTable, destinationOrder) {
        const sourceOrder = this.models["pos.order"].getBy("uuid", orderUuid);
        if (destinationTable && !destinationOrder && !this.tableHasOrders(destinationTable)) {
            return super.transferOrder(...arguments);
        }
        if (hasRevolutExposure(sourceOrder) || hasRevolutExposure(destinationOrder)) {
            explainGuard(this.dialog);
            return false;
        }
        return super.transferOrder(...arguments);
    },

    async mergeTableOrders(orderUuid, destinationTable) {
        const sourceOrder = this.models["pos.order"].getBy("uuid", orderUuid);
        if (!this.tableHasOrders(destinationTable)) {
            return super.mergeTableOrders(...arguments);
        }
        if (hasRevolutExposure(sourceOrder)) {
            explainGuard(this.dialog);
            return false;
        }
        return super.mergeTableOrders(...arguments);
    },
});

patch(SplitBillScreen.prototype, {
    async paySplittedOrder() {
        if (hasRevolutExposure(this.currentOrder)) {
            explainGuard(this.pos.dialog);
            return false;
        }
        return super.paySplittedOrder(...arguments);
    },

    async transferSplittedOrder() {
        if (hasRevolutExposure(this.currentOrder)) {
            explainGuard(this.pos.dialog);
            return false;
        }
        return super.transferSplittedOrder(...arguments);
    },
});
