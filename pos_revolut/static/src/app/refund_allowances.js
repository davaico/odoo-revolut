/** Display allowances; the server remains authoritative for refund allocation. */
export function refundAllowances(source, payments, currentUuid, factor) {
    let allocated = 0;
    let allocatedBase = 0;
    let allocatedTip = 0;
    for (const payment of payments) {
        if (payment.uuid === currentUuid) continue;
        const amount = Math.max(0, Math.round(-payment.amount * factor));
        allocated += amount;
        if (payment.payment_method_id?.use_payment_terminal !== "revolut") {
            allocatedBase += amount;
            continue;
        }
        const snapshot = payment.uiState?.revolutSnapshot;
        const base = snapshot?.base_amount_minor;
        const tip = snapshot?.tip_amount_minor;
        const known = Number.isSafeInteger(base) && base >= 0 &&
            Number.isSafeInteger(tip) && tip >= 0 && base + tip === amount;
        // Unknown components reserve both allowances until status recovers them.
        allocatedBase += known ? base : amount;
        allocatedTip += known ? tip : amount;
    }
    const maximumMinor = Math.max(0, source.return_total_minor - allocated);
    return {
        baseMinor: Math.max(0, Math.min(source.remaining_base_minor, source.return_base_minor - allocatedBase, maximumMinor)),
        tipMinor: Math.max(0, Math.min(source.remaining_tip_minor, source.return_tip_minor - allocatedTip, maximumMinor)),
        maximumMinor,
    };
}
