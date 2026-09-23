{
    "name": "POS Revolut",
    "version": "19.0.1.2.0",
    "category": "Sales/Point of Sale",
    "summary": "Configure a Revolut payment terminal for Point of Sale",
    "author": "Davai",
    "depends": ["point_of_sale"],
    "data": [
        "security/ir.model.access.csv",
        "views/pos_payment_method_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_revolut/static/src/app/**/*.js",
            "pos_revolut/static/src/app/**/*.xml",
        ],
        "web.assets_tests": ["pos_revolut/static/tests/tours/**/*.js"],
    },
    "license": "LGPL-3",
    "installable": True,
}
