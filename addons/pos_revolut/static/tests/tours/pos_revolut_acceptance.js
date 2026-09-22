import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_manager_configuration", {
    steps: () => [
        {
            trigger: ".o_form_button_edit",
            run: "click",
        },
        {
            trigger: ".o_form_editable .o_field_widget[name=payment_method_type] select",
            run: "select terminal",
        },
        {
            trigger: ".o_form_editable .o_field_widget[name=use_payment_terminal] select",
            run: "select revolut",
        },
        {
            trigger: ".o_field_widget[name=revolut_location_id] input",
            run: "edit 123e4567-e89b-12d3-a456-426614174000",
        },
        {
            trigger: ".o_field_widget[name=revolut_terminal_id] input",
            run: "edit 0e53f673-7705-473a-a263-89a3e7647c3d",
        },
        {
            trigger: ".o_field_widget[name=revolut_secret_reference] input",
            run: "edit ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: "button[name=action_revolut_check_connection]",
            run: "click",
        },
        {
            trigger: '.o_notification_content:contains("Counter 1 is online.")',
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_retail_starts", {
    steps: () => [
        ...Chrome.startPoS(),
        {
            trigger: ".product-screen .product-list",
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_starts", {
    steps: () => [
        ...Chrome.startPoS(),
        {
            trigger: ".floor-screen .floor-map",
        },
    ],
});
