import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_restaurant_starts", {
    steps: () => [
        ...Chrome.startPoS(),
        {
            trigger: ".floor-screen .floor-map",
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_checkout", {
    steps: () => [
        Chrome.startPoS(),
        {
            content: "Open the Restaurant table",
            trigger: ".floor-map .table:has(.label:contains('1')):not(.syncing)",
            run: "click",
        },
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
    ].flat(),
});
