import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { hasRevolutExposure } from "./payment_revolut";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { Base } from "@point_of_sale/app/models/related_models";
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

const { DateTime } = luxon;

export class RevolutPreset extends Base {
    static pythonModel = "pos.preset";

    get needsSlot() {
        return this.use_timing && !this.is_return;
    }
}

registry.category("pos_available_models").add(RevolutPreset.pythonModel, RevolutPreset);

export class RevolutPresetTimingDialog extends Component {
    static template = "pos_revolut.PresetTimingDialog";
    static components = { Dialog };
    static props = {
        days: Array, timezone: String, save: Function, getPayload: Function, close: Function,
    };

    setup() {
        this.state = useState({ date: this.props.days[0]?.date, saving: false, error: "" });
    }

    get selectedDay() {
        return this.props.days.find((day) => day.date === this.state.date);
    }

    dayLabel(day) {
        return DateTime.fromISO(day.date).toFormat("ccc dd LLL");
    }

    async selectSlot(slot) {
        if (this.state.saving) {
            return;
        }
        this.state.saving = true;
        this.state.error = "";
        try {
            await this.props.save(slot);
            this.props.getPayload(true);
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || error.message ||
                _t("The pickup time could not be saved. Please try again.");
        } finally {
            this.state.saving = false;
        }
    }
}

patch(PosOrder.prototype, {
    get presetRequirementsFilled() {
        return !this.presetIdentificationError && !this.presetSlotRequired;
    },

    get presetSlotRequired() {
        return this.config.use_presets && !this._isRefundOrder() &&
            this.preset_id?.needsSlot && !this.preset_time;
    },

    get presetPickupLabel() {
        if (!this.preset_time) {
            return "";
        }
        // Native 18 datetime fields are UTC SQL strings, including in IndexedDB.
        // Keep that representation when syncing instead of serializing Luxon.
        const date = DateTime.fromSQL(this.preset_time, { zone: "utc" })
            .setZone(this.preset_id?.calendar_tz || "UTC");
        return date.isValid ? date.toFormat("dd LLL yyyy HH:mm") : "";
    },

    export_for_printing() {
        return {
            ...super.export_for_printing(...arguments),
            presetName: this.config.use_presets && this.preset_id?.name,
            presetPickup: this.presetPickupLabel,
            presetTimezone: this.preset_id?.calendar_tz || "UTC",
        };
    },

    get presetIdentificationError() {
        if (!this.config.use_presets || this._isRefundOrder()) {
            return false;
        }
        if (this.preset_id?.identification === "name" &&
            !(this.partner_id || this.floating_order_name)) {
            return _t("Select a customer or enter an order name for this checkout preset.");
        }
        if (this.preset_id?.identification === "address" &&
            !(this.partner_id?.street || this.partner_id?.street2)) {
            return _t("Select a customer with an address for this checkout preset.");
        }
        return false;
    },

    setPreset(preset) {
        const available = [...this.config.available_preset_ids, this.config.default_preset_id];
        if (!this.config.use_presets || !preset || !available.includes(preset) ||
            preset.is_return || this._isRefundOrder() || hasRevolutExposure(this) ||
            this.revolut_has_authority_exposure ||
            (preset.company_id && preset.company_id.id !== this.company.id)) {
            return false;
        }
        this.update({ preset_id: preset, preset_time: false,
            fiscal_position_id: preset.fiscal_position_id || this.config.default_fiscal_position_id });
        this.set_pricelist(preset.pricelist_id || this.config.pricelist_id);
        return true;
    },

    updatePricelistAndFiscalPosition() {
        super.updatePricelistAndFiscalPosition(...arguments);
        if (this.config.use_presets && this.preset_id && !this._isRefundOrder()) {
            if (this.preset_id.fiscal_position_id) {
                this.update({ fiscal_position_id: this.preset_id.fiscal_position_id });
            }
            if (this.preset_id.pricelist_id) {
                this.set_pricelist(this.preset_id.pricelist_id);
            }
        }
    },
});

patch(PaymentScreen.prototype, {
    async _isOrderValid() {
        if (this.currentOrder.presetSlotRequired) {
            this.dialog.add(AlertDialog, {
                title: _t("Slot required"),
                body: _t("Choose an available pickup date and time using Pickup time before completing this order. If today has no slots, choose another date."),
            });
            return false;
        }
        const message = this.currentOrder.presetIdentificationError;
        if (message) {
            this.dialog.add(AlertDialog, { title: _t("Checkout preset"), body: message });
            return false;
        }
        return super._isOrderValid(...arguments);
    },
});

patch(PosStore.prototype, {
    async openPresetTiming(order = this.get_order()) {
        if (!order || order.finalized || !this.config.use_presets ||
            order._isRefundOrder() || !order.preset_id?.needsSlot) {
            return false;
        }
        const preset = order.preset_id;
        try {
            const availability = await this.data.call("pos.preset", "get_available_slots", [
                [preset.id], this.config.id, typeof order.id === "number" ? order.id : false,
            ]);
            return await makeAwaitable(this.dialog, RevolutPresetTimingDialog, {
                days: availability.days,
                timezone: availability.timezone,
                save: async (slot) => {
                    // Restaurant saves drafts in the background. Wait before changing
                    // context so an older save response cannot discard this selection.
                    await Promise.all([...(this.revolutRestaurantSyncs || [])]);
                    if (order.finalized || order.preset_id !== preset) {
                        throw new Error(_t("The order changed. Close scheduling and open it again."));
                    }
                    const previous = order.preset_time;
                    order.update({ preset_time: slot.time });
                    this.addPendingOrder([order.id]);
                    try {
                        // Explicitly sync this same order, including a captured draft.
                        // Changing the preset itself would reprice the authorized cart.
                        await this.syncAllOrders({ orders: [order], force: true, throw: true });
                    } catch (error) {
                        order.update({ preset_time: previous || false });
                        this.addPendingOrder([order.id]);
                        throw error;
                    }
                },
            });
        } catch (error) {
            this.dialog.add(AlertDialog, {
                title: _t("Pickup scheduling unavailable"),
                body: error.data?.message || error.message ||
                    _t("Pickup availability could not be loaded. Check your connection and try again."),
            });
            return false;
        }
    },

    createNewOrder() {
        const order = super.createNewOrder(...arguments);
        if (this.config.use_presets && !order.preset_id) {
            order.setPreset(this.config.default_preset_id);
        }
        return order;
    },

    set_order(order) {
        // Restaurant can reuse an empty draft created before presets were
        // configured. Apply the default only while it has no financial content.
        if (order?.state === "draft" && !order.preset_id && !order.lines.length &&
            !order.payment_ids.length && this.config.use_presets) {
            order.setPreset(this.config.default_preset_id);
        }
        return super.set_order(...arguments);
    },
});

patch(ControlButtons.prototype, {
    get revolutPresetLocked() {
        return !this.currentOrder || this.currentOrder._isRefundOrder() ||
            hasRevolutExposure(this.currentOrder) || this.currentOrder.revolut_has_authority_exposure;
    },

    async selectRevolutPreset() {
        if (this.revolutPresetLocked) {
            return;
        }
        const order = this.currentOrder;
        const presets = [...new Set([
            ...this.pos.config.available_preset_ids, this.pos.config.default_preset_id,
        ])].filter((preset) => preset && !preset.is_return &&
            (!preset.company_id || preset.company_id.id === this.pos.company.id));
        const preset = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t("Checkout preset"),
            list: presets.map((item) => ({ id: item.id, label: item.name, item,
                isSelected: item === order.preset_id })),
        });
        if (preset && this.currentOrder === order && order.setPreset(preset) &&
            preset.revolut_fulfilment === "take_away") {
            // Only an explicit Takeout selection removes the table. Applying a
            // default while opening a Restaurant table must retain its context.
            order.update({ table_id: false });
        }
    },
});
