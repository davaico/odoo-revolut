import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_admin_credential_authority", {
    steps: () => [
        { trigger: ".o_list_button_add", run: "click" },
        {
            trigger: ".o_field_widget[name=company_id] input",
            run: "edit Browser Revolut Company",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:not(.o_m2o_dropdown_option):contains('Browser Revolut Company')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=environment] select",
            run: "selectByLabel Sandbox",
        },
        {
            trigger: ".o_field_widget[name=secret_reference] input",
            run: "edit ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        },
        { trigger: ".o_form_button_save", run: "click" },
        {
            content: "The administrator saved the company-bound Merchant authority",
            trigger: ".o_form_renderer.o_form_saved .o_field_widget[name=secret_reference] span:contains('ODOO_REVOLUT_SECRET_TEST_TERMINAL')",
            run() {
                for (const name of ["company_id", "environment", "secret_reference"]) {
                    if (document.querySelector(`.o_field_widget[name=${name}] input, .o_field_widget[name=${name}] select`)) {
                        throw new Error(`The saved Merchant authority still permits ${name} editing`);
                    }
                }
            },
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_admin_register_grant", {
    steps: () => [
        {
            trigger: ".o_field_widget[name=revolut_user_ids] input",
            run: "edit A simple PoS man!",
        },
        {
            trigger: ".o-autocomplete--dropdown-item:not(.o_m2o_dropdown_option):contains('A simple PoS man!')",
            run: "click",
        },
        { trigger: ".o_form_button_save", run: "click" },
        {
            content: "The administrator saved the explicit cashier grant on this register",
            trigger: ".o_form_renderer.o_form_saved .o_field_widget[name=revolut_user_ids] .o_tag:contains('A simple PoS man!')",
        },
    ],
});
