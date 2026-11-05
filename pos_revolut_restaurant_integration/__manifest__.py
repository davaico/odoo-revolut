{
    "name": "POS Revolut Restaurant Integration",
    "version": "18.0.1.0.9",
    "category": "Sales/Point of Sale",
    "summary": "Use Revolut terminal payments on Odoo Restaurant registers",
    "author": "Davai",
    "depends": ["pos_revolut", "pos_restaurant"],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_revolut_restaurant_integration/static/src/app/restaurant_revolut.js",
            "pos_revolut_restaurant_integration/static/src/app/restaurant_revolut.xml",
        ],
        "web.assets_tests": ["pos_revolut_restaurant_integration/static/tests/tours/*.js"],
    },
    "license": "LGPL-3",
    "installable": True,
    "auto_install": True,
}
