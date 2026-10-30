import { registry } from "@web/core/registry";

function savedDatabaseAuthority(reference) {
    return {
        content: "The saved database authority hides its key and freezes its identity",
        trigger: `.o_form_renderer.o_form_saved .o_field_widget[name=secret_reference] span:contains('${reference}')`,
        run() {
            for (const name of ["company_id", "environment", "secret_reference", "source"]) {
                if (document.querySelector(`.o_field_widget[name=${name}] input, .o_field_widget[name=${name}] select`)) {
                    throw new Error(`The saved Merchant authority still permits ${name} editing`);
                }
            }
            if (document.querySelector(".o_field_widget[name=secret_key]")) {
                throw new Error("The saved Merchant authority exposes its key in the form");
            }
        },
    };
}

registry.category("web_tour.tours").add("pos_revolut_admin_database_credential", {
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
        { trigger: ".o_field_widget[name=environment] select", run: "selectByLabel Sandbox" },
        { trigger: ".o_field_widget[name=source] select", run: "selectByLabel Database" },
        {
            trigger: ".o_field_widget[name=secret_reference] input",
            run: "edit ODOO_REVOLUT_SECRET_BROWSER_DATABASE",
        },
        {
            trigger: ".o_field_widget[name=secret_key] input[type=password]",
            run: "edit synthetic-browser-database-key",
        },
        { trigger: ".o_form_button_save", run: "click" },
        savedDatabaseAuthority("ODOO_REVOLUT_SECRET_BROWSER_DATABASE"),
    ],
});

registry.category("web_tour.tours").add("pos_revolut_admin_rotate_database_credential", {
    steps: () => [
        { trigger: "button[name=action_rotate]", run: "click" },
        {
            content: "Rotation starts a new authority with an empty reference and key",
            trigger: ".o_field_widget[name=secret_key] input[type=password]",
            run() {
                if (this.anchor.value || document.querySelector(".o_field_widget[name=secret_reference] input").value) {
                    throw new Error("Rotation copied the original secret or reference");
                }
            },
        },
        {
            trigger: ".o_field_widget[name=secret_reference] input",
            run: "edit ODOO_REVOLUT_SECRET_BROWSER_DATABASE_ROTATED",
        },
        {
            trigger: ".o_field_widget[name=secret_key] input[type=password]",
            run: "edit synthetic-browser-rotated-key",
        },
        { trigger: ".o_form_button_save", run: "click" },
        savedDatabaseAuthority("ODOO_REVOLUT_SECRET_BROWSER_DATABASE_ROTATED"),
    ],
});

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
