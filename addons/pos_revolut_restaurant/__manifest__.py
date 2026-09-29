{
    "name": "POS Revolut Restaurant",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "Guard restaurant bill splits and transfers during Revolut payment",
    "author": "Davai",
    "depends": ["pos_revolut", "pos_restaurant"],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_revolut_restaurant/static/src/app/**/*.js",
        ],
        "web.assets_tests": [
            "pos_revolut_restaurant/static/tests/tours/**/*.js",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "auto_install": True,
}
