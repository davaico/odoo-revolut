import { registry } from "@web/core/registry";

const ORDER_UUID = "860724e8-c507-40b4-bcbe-970bd3b60055";
const HIDDEN_UUID = "18a1fc19-8c42-4cd9-b715-f83087f90055";
const INTENT_ID = "ac55159c-b656-4ac9-989a-0f46d36e0055";

registry.category("web_tour.tours").add("pos_revolut_manager_reconciles_register", {
    steps: () => [
        {
            trigger: `.o_list_view .o_data_row:contains('${ORDER_UUID}')`,
            run() {
                if (document.body.textContent.includes(HIDDEN_UUID)) {
                    throw new Error("A manager can see another register's payment work");
                }
            },
        },
        { trigger: `.o_list_view .o_data_row .o_data_cell[name='order_uuid']:contains('${ORDER_UUID}')`, run: "click" },
        { trigger: ".o_form_view button[name='action_revolut_open_association']", run: "click" },
        { trigger: ".modal .o_field_widget[name='intent_reference'] input", run: `edit ${INTENT_ID}` },
        { trigger: ".modal button[name='action_associate']", run: "click" },
        { trigger: `.o_form_view .o_field_widget[name='revolut_payment_intent_id']:contains('${INTENT_ID}')` },
        { trigger: ".o_form_view button[name='action_revolut_reconcile']", run: "click" },
        { trigger: ".o_form_view .o_field_widget[name='audit_ids'] .o_data_row:contains('reconcile')" },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_manager_revoked_worklist", {
    steps: () => [
        {
            trigger: ".o_list_view .o_list_table tbody:not(:has(.o_data_row))",
            run() {
                if (document.querySelector(".o_list_view .o_data_row") ||
                    document.body.textContent.includes(ORDER_UUID) ||
                    document.body.textContent.includes(HIDDEN_UUID)) {
                    throw new Error("Revoked register access still exposes financial work");
                }
            },
        },
    ],
});
