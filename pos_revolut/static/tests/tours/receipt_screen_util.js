export * from "@point_of_sale/../tests/tours/utils/receipt_screen_util";

export function paymentLineContains(method, amount) {
    return {
        content: `The native receipt shows ${method} paid ${amount}`,
        trigger: `.receipt-screen .pos-receipt .paymentlines:contains('${method}'):contains('${amount}')`,
    };
}
