import { patch } from "@web/core/utils/patch";
import { roundDecimals, roundPrecision } from "@web/core/utils/numbers";
import { ComboConfiguratorPopup } from "@point_of_sale/app/store/combo_configurator_popup/combo_configurator_popup";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { hasRevolutExposure } from "./payment_revolut";

function hasQuantityChoices(product) {
    return product.combo_ids.some((combo) => combo.qty_free !== 1 || combo.qty_max !== 1);
}

// Extra selections keep the maintained allocation: included choices share the
// parent's price; additional choices pay their base price. Every selected unit
// retains its own native child line and attribute configuration.
function comboPrices(product, selections, order, models) {
    const currency = order.currency;
    const convert = (amount, source) => source.id === currency.id
        ? amount : amount * currency.rate / source.rate;
    // Ordinary choices retain native decimal allocation (including the final
    // remainder), while configured quantity choices use the currency quantum.
    const quantityMode = hasQuantityChoices(product);
    const digits = currency.decimal_places || models["decimal.precision"].find((dp) => dp.name === "Product Price").digits;
    const round = (amount) => quantityMode
        ? roundPrecision(amount, currency.rounding) : roundDecimals(amount, digits);
    const included = [], additional = [];
    // Native ordinary selections come from a numeric combo-ID keyed object.
    const combos = quantityMode ? product.combo_ids : [...product.combo_ids].sort((left, right) => left.id - right.id);
    for (const combo of combos) {
        const selected = selections.filter((selection) => selection.combo_item_id.combo_id === combo)
            .sort((left, right) => left.combo_item_id.id - right.combo_item_id.id);
        included.push(...selected.slice(0, combo.qty_free));
        additional.push(...selected.slice(combo.qty_free));
    }
    const parentPrice = product.get_price(order.pricelist_id, 1);
    const base = (selection) => convert(selection.combo_item_id.combo_id.base_price,
        selection.combo_item_id.combo_id.currency_id);
    const denominator = included.reduce((total, selection) => total + base(selection), 0);
    let remaining = parentPrice;
    const prices = new Map();
    included.forEach((selection, index) => {
        let price = denominator ? round(base(selection) * parentPrice / denominator) : 0;
        remaining -= price;
        if (index === included.length - 1) {
            price += remaining;
            remaining = 0;
        }
        prices.set(selection, price);
    });
    const extraDenominator = additional.reduce((total, selection) =>
        total + selection.combo_item_id.combo_id.base_price, 0);
    additional.forEach((selection, index) => {
        let price = round(base(selection));
        if (remaining && extraDenominator) {
            const share = round(base(selection) * parentPrice / extraDenominator);
            price += share;
            remaining -= share;
            if (index === additional.length - 1) {
                price += remaining;
                remaining = 0;
            }
        }
        prices.set(selection, price);
    });
    return selections.map((selection) => {
        const attributes = selection.configuration?.attribute_value_ids || [];
        const attributeExtra = attributes.reduce((total, value) => {
            const attribute = typeof value === "number"
                ? models["product.template.attribute.value"].get(value) : value;
            return total + (attribute?.attribute_id.create_variant !== "always"
                ? attribute?.price_extra || 0 : 0);
        }, 0);
        return {
            selection,
            price: prices.get(selection) + attributeExtra +
                convert(selection.combo_item_id.extra_price, selection.combo_item_id.currency_id),
        };
    });
}

patch(ComboConfiguratorPopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.revolutQuantityMode = hasQuantityChoices(this.props.product);
        this.state.revolutSelections = [];
    },

    hasMultipleChoices() {
        return this.revolutQuantityMode || super.hasMultipleChoices(...arguments);
    },

    autoSelectSingleChoices() {
        if (!this.revolutQuantityMode) {
            return super.autoSelectSingleChoices(...arguments);
        }
        for (const combo of this.props.product.combo_ids) {
            const choices = this.getAvailableComboLines(combo);
            if (choices.length === 1 && !choices[0].product_id.isConfigurable()) {
                for (let count = 0; count < combo.qty_free; count++) {
                    this.state.revolutSelections.push({ comboItemId: choices[0].id });
                }
            }
        }
    },

    revolutSelectedQuantity(item) {
        return this.state.revolutSelections.filter((selection) => selection.comboItemId === item.id).length;
    },

    revolutComboQuantity(combo) {
        return this.getSelectedComboItems().filter((selection) => selection.combo_item_id.combo_id === combo).length;
    },

    areAllCombosSelected() {
        if (!this.revolutQuantityMode) {
            return super.areAllCombosSelected(...arguments);
        }
        return this.state.revolutSelections.length > 0 && this.props.product.combo_ids.every((combo) => {
            const count = this.revolutComboQuantity(combo);
            return count >= combo.qty_free && count <= combo.qty_max;
        });
    },

    getSelectedComboItems() {
        if (!this.revolutQuantityMode) {
            return super.getSelectedComboItems(...arguments);
        }
        return this.state.revolutSelections.map((selection) => ({
            combo_item_id: this.pos.models["product.combo.item"].get(selection.comboItemId),
            configuration: selection.configuration,
        }));
    },

    async onClickProduct({ product, combo_item }, event) {
        if (!this.revolutQuantityMode) {
            return super.onClickProduct(...arguments);
        }
        return this.revolutChangeQuantity(combo_item, 1);
    },

    async revolutChangeQuantity(item, delta) {
        if (delta < 0) {
            const index = this.state.revolutSelections.findLastIndex((selection) => selection.comboItemId === item.id);
            if (index >= 0) {
                this.state.revolutSelections.splice(index, 1);
            }
            return;
        }
        if (this.revolutComboQuantity(item.combo_id) >= item.combo_id.qty_max) {
            return;
        }
        let configuration;
        if (item.product_id.needToConfigure()) {
            configuration = await this.pos.openConfigurator(item.product_id, { hideAlwaysVariants: true });
            if (!configuration) {
                return;
            }
        }
        if (this.revolutComboQuantity(item.combo_id) < item.combo_id.qty_max) {
            this.state.revolutSelections.push({ comboItemId: item.id, configuration });
        }
    },

    get revolutComboTotal() {
        const prices = comboPrices(this.props.product, this.getSelectedComboItems(),
            this.pos.get_order(), this.pos.models);
        return this.env.utils.formatCurrency(prices.reduce((total, { selection, price }) =>
            total + this.pos.getProductPrice(selection.combo_item_id.product_id, price), 0));
    },
});

function repriceCombo(parent) {
    const order = parent.order_id;
    if (parent.qty <= 0 ||
        parent.refunded_orderline_id || hasRevolutExposure(order)) {
        return;
    }
    const quantityMode = hasQuantityChoices(parent.product_id);
    if (!quantityMode && parent.price_type !== "original") {
        return;
    }
    if (parent.combo_line_ids.some((line) =>
        !Number.isInteger(line.qty / parent.qty) || line.qty / parent.qty <= 0)) {
        return;
    }
    const selections = parent.combo_line_ids.flatMap((line) => {
        const quantity = line.qty / parent.qty;
        return Array.from({ length: quantity }, () => ({
            line, combo_item_id: line.combo_item_id,
            configuration: { attribute_value_ids: line.attribute_value_ids },
        }));
    });
    const totals = new Map(parent.combo_line_ids.map((line) => [line, 0]));
    for (const { selection, price } of comboPrices(parent.product_id, selections, order, parent.models)) {
        totals.set(selection.line, totals.get(selection.line) + price);
    }
    for (const [line, total] of totals) {
        if (quantityMode || line.price_type === "original") {
            line.set_unit_price(total / (line.qty / parent.qty));
        }
    }
    parent.set_unit_price(0);
    order.recomputeOrderData();
}

patch(PosStore.prototype, {
    async addLineToOrder(values, order, options = {}, configure = true) {
        const line = await super.addLineToOrder(...arguments);
        if (configure && line?.combo_line_ids.length) {
            if (hasQuantityChoices(line.product_id)) {
                for (const child of line.combo_line_ids) {
                    child.set_quantity(line.qty, true);
                }
            }
            repriceCombo(line);
        }
        return line;
    },
});

patch(PosOrder.prototype, {
    set_pricelist() {
        const result = super.set_pricelist(...arguments);
        for (const line of this.lines.filter((line) => line.combo_line_ids.length)) {
            repriceCombo(line);
        }
        return result;
    },
});
