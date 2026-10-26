{
    "name": "POS Revolut",
    "version": "19.0.1.18.16",
    "category": "Sales/Point of Sale",
    "summary": "Configure a Revolut payment terminal for Point of Sale",
    "description": """
Connect Odoo Point of Sale to a Revolut payment terminal. Supports retail and
Restaurant registers, split payments, terminal-selected tips, full and partial
refunds, interrupted-payment recovery and discovery of external refunds.
Checkout completes after payment verification and native Odoo validation.

Requires an administered Odoo server, a Revolut Merchant account, authorized
Merchant API credentials, an online compatible terminal in Pay at Counter mode,
and permissions for terminal operations and payments_report creation, polling
and download. Dependencies: point_of_sale and pos_restaurant. Verified runtime:
Odoo Community 19.0.20260908 and PostgreSQL 16.14. Other builds and Enterprise
have not been verified.

External service and data: the server contacts the Revolut Merchant API for
terminal discovery, payments, refunds, status checks and payment reports. It
sends amounts, currency, location and terminal identifiers, fulfilment type,
the integration partner identifier, technical order/payment-line identifiers, provider
transaction references, refund/idempotency references and report filters/options.
Merchant credentials authenticate server-side calls. Card details are handled
by the terminal and Revolut; this addon does not send customer contact details
or product lines. Odoo records payment/refund references, verified amounts and
statuses for recovery and reconciliation.

Use terminal-selected tips; Odoo-entered tips and Restaurant Add tips after
payment are unsupported. Timed Takeout requires a pickup slot before payment.
Retail currently maps fulfilment to Eat In. Internet access is required.

Free and open source under LGPL-3, maintained by Davai. Independent integration,
not an official or certified Revolut or Odoo product. Revolut hardware, account
and processing charges are separate from the free addon.
""",
    "author": "Davai",
    "images": ["static/description/revolut-terminal.jpg"],
    "depends": ["point_of_sale", "pos_restaurant"],
    "data": [
        "security/ir.model.access.csv",
        "security/revolut_reconciliation_rules.xml",
        "data/revolut_reconciliation_cron.xml",
        "views/pos_payment_method_views.xml",
        "views/pos_config_views.xml",
        "views/revolut_credential_views.xml",
        "views/revolut_reconciliation_views.xml",
        "views/revolut_refund_views.xml",
        "views/external_refund_completion_views.xml",
        "views/revolut_cart_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_revolut/static/src/app/**/*.js",
            "pos_revolut/static/src/app/**/*.xml",
            "pos_revolut/static/src/app/**/*.scss",
        ],
        "web.assets_tests": ["pos_revolut/static/tests/tours/**/*.js"],
    },
    "license": "LGPL-3",
    "installable": True,
    "post_init_hook": "post_init_hook",
}
