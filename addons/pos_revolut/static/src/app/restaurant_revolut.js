import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { SplitBillScreen } from "@pos_restaurant/app/split_bill_screen/split_bill_screen";
import { hasRevolutExposure } from "@pos_revolut/app/payment_revolut";
import { TipScreen } from "@pos_restaurant/app/tip_screen/tip_screen";
import { PosData } from "@point_of_sale/app/models/data_service";

function explainGuard(dialog) {
    dialog.add(AlertDialog, {
        title: _t("Revolut payment attached to this order"),
        body: _t("Check or reconcile the Revolut payment before splitting or merging this order. A table change that keeps the same order is allowed."),
    });
}

patch(PosData.prototype, {
    write(model, ids, values) {
        if (model === "restaurant.table" && values.parent_id) {
            // Native drag-linking writes independently of transferOrder's
            // result, and write() updates the browser before its RPC returns.
            const changing = ids.filter((id) =>
                this.models[model].get(id)?.parent_id?.id !== values.parent_id);
            if (!changing.length) {
                return super.write(...arguments);
            }
            const tables = new Set([...changing, values.parent_id]);
            let previousSize;
            do {
                previousSize = tables.size;
                for (const table of this.models["restaurant.table"].getAll()) {
                    if (table.parent_id && (tables.has(table.id) || tables.has(table.parent_id.id))) {
                        tables.add(table.id);
                        tables.add(table.parent_id.id);
                    }
                }
            } while (tables.size !== previousSize);
            if (this.models["pos.order"].some((order) => !order.finalized &&
                tables.has(order.table_id?.id) &&
                (hasRevolutExposure(order) || order.revolut_has_authority_exposure))) {
                explainGuard(this.dialog);
                return [];
            }
        }
        return super.write(...arguments);
    },
});

patch(PosStore.prototype, {
    async syncAllOrders() {
        const request = super.syncAllOrders(...arguments);
        const pending = this.revolutRestaurantSyncs ||= new Set();
        pending.add(request);
        try {
            return await request;
        } finally {
            pending.delete(request);
        }
    },

    async transferOrder(orderUuid, destinationTable) {
        // Opening the floor starts an unawaited native draft save. Native 18
        // skips another save of that order while it is in flight, so wait
        // before changing its table or an older response can undo the move.
        await Promise.all([...(this.revolutRestaurantSyncs || [])]);
        const sourceOrder = this.models["pos.order"].getBy("uuid", orderUuid);
        const destinationOrders = this.getActiveOrdersOnTable(destinationTable);
        // Odoo 18 performs both a table move and a merge through transferOrder.
        // The same table or an empty destination preserves financial identity.
        if (sourceOrder.table_id?.id === destinationTable.id || !destinationOrders.length) {
            return super.transferOrder(...arguments);
        }
        if (hasRevolutExposure(sourceOrder) || destinationOrders.some(hasRevolutExposure)) {
            explainGuard(this.dialog);
            return false;
        }
        return super.transferOrder(...arguments);
    },
});

patch(SplitBillScreen.prototype, {
    async preSplitOrder(originalOrder, newOrder) {
        await super.preSplitOrder(...arguments);
        if (originalOrder.preset_id) {
            // Native 18 clones the lines but has no preset context of its own.
            newOrder.update({ preset_id: originalOrder.preset_id,
                preset_time: originalOrder.preset_time,
                fiscal_position_id: originalOrder.fiscal_position_id,
                pricelist_id: originalOrder.pricelist_id });
        }
    },

    async createSplittedOrder() {
        if (hasRevolutExposure(this.currentOrder)) {
            explainGuard(this.pos.dialog);
            return false;
        }
        return super.createSplittedOrder(...arguments);
    },
});

patch(TipScreen.prototype, {
    async validateTip() {
        if (hasRevolutExposure(this.pos.get_order())) {
            this.dialog.add(AlertDialog, { title: _t("Revolut terminal tip"),
                body: _t("Revolut records terminal tips during payment. Post-payment tip adjustment is unsupported for this order.") });
            return false;
        }
        return super.validateTip(...arguments);
    },
});
