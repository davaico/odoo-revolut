const POLL_INTERVAL_MS = 1000;
const PAYMENT_TIMEOUT_MS = 60000;
const FINAL_FAILURE_STATES = new Set(["declined", "failed", "cancelled", "unresolved"]);
const TERMINAL_FAILURE_STATES = new Set(["terminal_unavailable", "terminal_check_failed"]);

export class ForegroundTimeout extends Error {}

export function isRevolut(line) {
    return line?.payment_method_id?.use_payment_terminal === "revolut";
}

export function isRevolutRefund(line) {
    return isRevolut(line) && (line.amount < 0 || line.pos_order_id?.isRefund);
}

function financialStartMayHaveOccurred(line) {
    const state = line.uiState || {};
    return Boolean(state.revolutStarted || state.revolutStarting ||
        state.revolutOperationId || state.revolutSnapshot ||
        state.revolutOriginalOperationId || line.transaction_id || line.payment_ref_no ||
        (state.revolutUndispatched !== true &&
            ["retry", "waitingCard", "waitingCancel"].includes(line.getPaymentStatus())));
}

export function paymentActions(line) {
    if (!isRevolut(line)) {
        return {
            canEditAmount: true, canDelete: true, blocksCheckout: false,
            blocksAlternativeTender: false, hasExposure: false, retrySafe: false,
            shouldCancelBeforeDelete: false,
        };
    }
    const state = line.uiState || {};
    const refund = isRevolutRefund(line);
    const refundStarted = refund && financialStartMayHaveOccurred(line);
    const unstartedRefund = refund && !refundStarted;
    const failedRefund = refund && state.revolutSnapshot?.state === "failed";
    const locked = state.revolutDiscovering ||
        (!unstartedRefund && !failedRefund && !state.revolutSelectingAllocation &&
        !state.revolutSnapshot?.retry_safe &&
        (financialStartMayHaveOccurred(line) ||
            (state.revolutUndispatched !== true && line.getPaymentStatus() === "waiting")));
    const reconcile = (state.revolutDiscovering || !unstartedRefund) &&
        !failedRefund && (locked || refund) &&
        state.revolutSnapshot?.state !== "verified";
    return {
        canEditAmount: !locked && !failedRefund,
        canDelete: !locked,
        shouldCancelBeforeDelete: locked && state.revolutSnapshot?.state !== "verified",
        blocksCheckout: reconcile || failedRefund,
        blocksAlternativeTender: reconcile,
        hasExposure: locked || state.revolutStarting || Boolean(line.transaction_id) ||
            line.getPaymentStatus() === "done",
        refundException: (!state.revolutDiscovering && unstartedRefund) || failedRefund,
        retrySafe: !state.revolutDiscovering &&
            (state.revolutSnapshot?.retry_safe === true ||
                (state.revolutUndispatched === true && !financialStartMayHaveOccurred(line))),
    };
}

export function orderActions(order) {
    const lines = order?.payment_ids || [];
    return {
        blocksCheckout: lines.some((line) => paymentActions(line).blocksCheckout),
        blocksAlternativeTender: lines.some((line) => paymentActions(line).blocksAlternativeTender),
        hasExposure: lines.some((line) => paymentActions(line).hasExposure),
        hasRefundException: lines.some((line) => paymentActions(line).refundException),
        electronicPaymentInProgress: lines.some((line) => line.payment_status &&
            !["done", "reversed"].includes(line.payment_status) &&
            !paymentActions(line).refundException),
    };
}

export function paymentOutcome(line) {
    const snapshot = line.uiState?.revolutSnapshot;
    if (snapshot?.state === "verified") {
        return "verified";
    }
    if (isRevolutRefund(line)) {
        return line.uiState?.revolutLocalOutcome || snapshot?.local_outcome || snapshot?.state;
    }
    return TERMINAL_FAILURE_STATES.has(snapshot?.provider_state)
        ? snapshot.provider_state
        : line.uiState?.revolutLocalOutcome || snapshot?.local_outcome || snapshot?.state;
}

export function restorePaymentLine(line) {
    const started = isRevolut(line) && (financialStartMayHaveOccurred(line) ||
        (line.uiState.revolutUndispatched !== true && line.getPaymentStatus() === "waiting"));
    line.uiState.revolutStarting = false;
    line.uiState.revolutDiscovering = false;
    if (started) {
        line.uiState.revolutStarted = true;
        line.uiState.revolutUndispatched = false;
    }
    if (isRevolut(line) &&
        (started || line.uiState.revolutUndispatched) &&
        line.getPaymentStatus() !== "done") {
        line.setPaymentStatus("retry");
    }
}

export function paymentResponseSuccessful(line, successful) {
    return isRevolut(line) ? line.uiState.revolutSnapshot?.state === "verified" : successful;
}

const systemClock = {
    now: () => Date.now(),
    wait: (duration) => new Promise((resolve) => setTimeout(resolve, duration)),
    async before(promise, deadline) {
        let timer;
        try {
            return await Promise.race([
                promise,
                new Promise((resolve, reject) => {
                    timer = setTimeout(() => reject(new ForegroundTimeout()), Math.max(0, deadline - Date.now()));
                }),
            ]);
        } finally {
            clearTimeout(timer);
        }
    },
};

// A single owner follows one logical order/payment-line UUID pair, even when a
// failed payment is replaced or a reloaded line object is rebound to it.
export class RevolutPaymentState {
    constructor({ adapter, methodId, sessionId, currencyId, clock = systemClock }) {
        this.adapter = adapter;
        this.methodId = methodId;
        this.sessionId = sessionId;
        this.currencyId = currencyId;
        this.clock = clock;
        this.lines = new Map();
    }

    owner(order, line) {
        const key = `${order.uuid}:${line.uuid}`;
        let owner = this.lines.get(key);
        if (!owner) {
            owner = { order, line, request: null, cancellation: null, screenRequest: null };
            this.lines.set(key, owner);
        } else {
            owner.order = order;
            owner.line = line;
        }
        return owner;
    }

    screenRequest(order, line, invoke, { checkOnly = false } = {}) {
        const owner = this.owner(order, line);
        if (owner.screenRequest) {
            return owner.screenRequest;
        }
        if (financialStartMayHaveOccurred(line)) {
            // Odoo's pay() overwrites retry with waiting before calling us.
            line.uiState.revolutStarted = true;
            line.uiState.revolutUndispatched = false;
        }
        owner.checkOnly = checkOnly;
        const request = Promise.resolve().then(invoke);
        owner.screenRequest = request;
        return request.finally(() => {
            if (owner.screenRequest === request) {
                owner.screenRequest = null;
                owner.checkOnly = false;
            }
        });
    }

    async screenCancel(order, line, resume, terminalIdle) {
        const owner = this.owner(order, line);
        line.setPaymentStatus("waitingCancel");
        const safe = await this.cancel(order, line);
        if (line.uiState.revolutSnapshot?.state === "verified") {
            line.setPaymentStatus("done");
            if (!owner.screenRequest) {
                await resume();
            }
        } else if (safe || !owner.screenRequest) {
            line.setPaymentStatus("retry");
            terminalIdle();
        } else {
            line.setPaymentStatus("waitingCard");
        }
        return safe;
    }

    request(order, line, { checkOnly = false } = {}) {
        const owner = this.owner(order, line);
        if (owner.request) {
            return owner.request;
        }
        const request = this.waitForResult(owner, checkOnly || owner.checkOnly);
        owner.request = request;
        request.finally(() => {
            if (owner.request === request) {
                owner.request = null;
            }
        });
        return request;
    }

    async waitForResult(owner, checkOnly) {
        const { order, line } = owner;
        owner.cancelDiscovery = false;
        const refund = isRevolutRefund(line);
        const pollMethod = refund ? "revolut_poll_refund" : "revolut_poll_payment";
        const started = financialStartMayHaveOccurred(line);
        let deadline = this.clock.now() + PAYMENT_TIMEOUT_MS;
        line.uiState.revolutUndispatched = !started;
        line.uiState.revolutDiscovering = true;
        line.setPaymentStatus("waiting");
        try {
            if (refund) {
                try {
                    await this.clock.before(this.adapter.restoreRefundOriginals(order), deadline);
                } catch (error) {
                    if (started) {
                        throw error;
                    }
                    line.uiState.revolutDiscovering = false;
                    this.adapter.discardRefund(line);
                    this.adapter.showPreparationError(line, "originals");
                    return false;
                }
            }
            let result = line.uiState.revolutSnapshot;
            let discovered = false;
            if (!result?.operation_id) {
                result = await this.clock.before(this.adapter.call(
                    refund ? "revolut_find_refund" : "revolut_find_payment",
                    [[this.methodId], order.uuid, line.uuid]
                ), deadline);
                discovered = Boolean(result);
            }
            if (result?.operation_id) {
                line.uiState.revolutStarted = true;
                line.uiState.revolutUndispatched = false;
                this.remember(line, result);
            }
            if (owner.cancelDiscovery) {
                if (result?.state === "verified") {
                    await this.adapter.setVerified(line, result);
                    return true;
                }
                if (!started && !result) {
                    line.uiState.revolutLocalOutcome = "discovery_cancelled";
                }
                return false;
            }
            if (!result && started) {
                // A lost start response cannot prove that dispatch did not occur.
                this.showError(line, "interrupted");
                return false;
            }
            if (checkOnly && (!result || result.retry_safe)) {
                // Checking a rejected or provider-final attempt never starts
                // a new charge. Only the cashier's explicit resume may do so.
                return false;
            }
            if (!result || (!refund && result.retry_safe && !discovered)) {
                const previousSnapshot = result;
                const previousOperationId = result?.retry_safe ? result.operation_id : false;
                let originalOperationId = false;
                let authorization = false;
                let refundAllocation = false;
                if (refund) {
                    line.uiState.revolutOperationId = false;
                    let sources;
                    try {
                        sources = await this.clock.before(this.adapter.call("revolut_refund_sources", [
                            [this.methodId], this.sessionId, this.currencyId,
                            this.adapter.financialSnapshot(order),
                        ]), deadline);
                    } catch (error) {
                        line.uiState.revolutDiscovering = false;
                        this.adapter.discardRefund(line);
                        this.adapter.showPreparationError(line, "sources", error?.data?.message);
                        return false;
                    }
                    if (!Array.isArray(sources) || !sources.length) {
                        line.uiState.revolutDiscovering = false;
                        this.adapter.discardRefund(line);
                        this.adapter.showPreparationError(line, "balance");
                        return false;
                    }
                    if (owner.cancelDiscovery) {
                        return false;
                    }
                    const allocation = await this.adapter.chooseAllocation(sources, line);
                    if (!allocation) {
                        line.uiState.revolutDiscovering = false;
                        this.adapter.discardRefund(line);
                        return false;
                    }
                    if (owner.cancelDiscovery) {
                        return false;
                    }
                    originalOperationId = allocation.operationId;
                    refundAllocation = allocation;
                    deadline = this.clock.now() + PAYMENT_TIMEOUT_MS;
                    line.uiState.revolutDiscovering = false;
                    this.adapter.setRefundAmount(line, allocation.amount);
                    line.uiState.revolutOriginalOperationId = originalOperationId;
                } else {
                    try {
                        authorization = await this.clock.before(this.adapter.preparePayment(order, line), deadline);
                        if (authorization?.status !== "prepared") {
                            throw new Error(authorization?.message || "Review or approve the current cart before payment.");
                        }
                    } catch (error) {
                        line.uiState.revolutDiscovering = false;
                        if (!previousSnapshot) {
                            line.uiState.revolutStarted = false;
                            line.uiState.revolutUndispatched = true;
                        }
                        line.uiState.revolutStartRejected = "authority_required";
                        line.uiState.revolutLocalOutcome = "authority_required";
                        line.uiState.revolutRejectionMessage = error?.data?.message || error.message;
                        this.showError(line, "authority_required");
                        return false;
                    }
                }
                line.uiState.revolutPreviousOperationId = previousOperationId;
                line.uiState.revolutSnapshot = false;
                line.uiState.revolutOperationId = false;
                line.uiState.revolutDiscovering = false;
                line.uiState.revolutStarted = true;
                line.uiState.revolutUndispatched = false;
                line.uiState.revolutStartRejected = false;
                line.uiState.revolutRejectionMessage = false;
                line.uiState.revolutMessage = false;
                line.uiState.revolutStarting = true;
                try {
                    result = await this.clock.before(this.adapter.call(
                        refund ? "revolut_start_refund" : "revolut_start_payment",
                        [[this.methodId], this.sessionId, order.uuid, line.uuid,
                            line.amount, this.currencyId,
                            ...(!refund ? [previousOperationId] : []),
                            this.adapter.financialSnapshot(order),
                            ...(refund ? [originalOperationId,
                                refundAllocation.baseAmountMinor ?? null, refundAllocation.tipAmountMinor ?? null]
                                : [authorization.authorization_id, authorization.cart_version, authorization.tender_revision])]
                    ), deadline);
                } finally {
                    line.uiState.revolutStarting = false;
                }
                // Only the direct start response can prove that this request
                // was rejected before dispatch. Exceptions and empty lookups
                // retain the uncertain-start guards.
                const rejectedBusy = !refund && result?.start_rejected === "terminal_busy";
                const rejectedSnapshot = result?.start_rejected === "snapshot_invalid" &&
                    !started && !previousSnapshot && previousOperationId === false;
                if ((rejectedBusy || rejectedSnapshot) &&
                    result.dispatched === false && result.order_uuid === order.uuid &&
                    result.payment_line_uuid === line.uuid &&
                    result.previous_operation_id === previousOperationId &&
                    !result.operation_id && !result.order_id &&
                    !result.payment_intent_id && !result.payment_id && !result.refund_id &&
                    !line.uiState.revolutSnapshot && !line.uiState.revolutOperationId &&
                    !line.transaction_id && !line.payment_ref_no) {
                    if (previousOperationId) {
                        this.remember(line, previousSnapshot);
                    }
                    if (refund) {
                        // Selection alone is not a dispatched refund. The
                        // rejected start created no reservation for this source.
                        line.uiState.revolutOriginalOperationId = false;
                    }
                    line.uiState.revolutStarted = false;
                    line.uiState.revolutUndispatched = true;
                    line.uiState.revolutStartRejected = result.start_rejected;
                    line.uiState.revolutLocalOutcome = result.start_rejected;
                    line.uiState.revolutRejectionMessage = rejectedSnapshot ? result.message : false;
                    this.showError(line, result.start_rejected);
                    return false;
                }
                if (!result?.operation_id) {
                    this.showError(line, "interrupted");
                    return false;
                }
            } else if (!result?.operation_id) {
                this.showError(line, "interrupted");
                return false;
            } else if (result.state !== "verified" && !result.retry_safe) {
                line.uiState.revolutDiscovering = false;
                line.uiState.revolutOperationId = result.operation_id;
                result = await this.clock.before(this.operationCall(pollMethod, order, line), deadline);
            }
            line.uiState.revolutDiscovering = false;
            this.remember(line, result);
            while (this.clock.now() < deadline) {
                if (owner.cancellation) {
                    await this.clock.before(owner.cancellation, deadline);
                }
                result = line.uiState.revolutSnapshot;
                if (result.state === "verified") {
                    await this.adapter.setVerified(line, result);
                    return true;
                }
                if (FINAL_FAILURE_STATES.has(result.state)) {
                    this.showError(line, result.local_outcome || result.state);
                    return false;
                }
                line.setPaymentStatus("waitingCard");
                await this.clock.before(this.clock.wait(POLL_INTERVAL_MS), deadline);
                if (!owner.cancellation) {
                    this.remember(line, await this.clock.before(
                        this.operationCall(pollMethod, order, line), deadline
                    ));
                }
            }
            throw new ForegroundTimeout();
        } catch (error) {
            if (line.uiState.revolutSnapshot?.state === "verified") {
                await this.adapter.setVerified(line, line.uiState.revolutSnapshot);
                return true;
            }
            const failure = error instanceof ForegroundTimeout ? "timed_out" : "interrupted";
            const outcome = !financialStartMayHaveOccurred(line) && line.uiState.revolutUndispatched
                ? `discovery_${failure}` : failure;
            line.uiState.revolutLocalOutcome = outcome;
            if (outcome === "timed_out" && line.uiState.revolutOperationId) {
                this.operationCall(refund ? "revolut_mark_refund_timeout" : "revolut_mark_timeout", order, line)
                    .catch(() => {});
            }
            this.showError(line, outcome);
            return false;
        } finally {
            line.uiState.revolutDiscovering = false;
        }
    }

    operationCall(method, order, line) {
        return this.adapter.call(method, [
            [this.methodId], line.uiState.revolutOperationId, order.uuid, line.uuid,
        ]);
    }

    remember(line, result) {
        const previous = line.uiState.revolutSnapshot;
        if (previous?.state === "verified" ||
            (previous?.operation_id === result.operation_id && previous.retry_safe &&
                !result.retry_safe && result.state !== "verified") ||
            (previous?.operation_id && previous.operation_id !== result.operation_id &&
                result.operation_id === line.uiState.revolutPreviousOperationId)) {
            return;
        }
        line.uiState.revolutSnapshot = result;
        line.uiState.revolutOperationId = result.operation_id;
        line.uiState.revolutStarted = true;
        line.uiState.revolutUndispatched = false;
        line.uiState.revolutStartRejected = false;
        line.uiState.revolutRejectionMessage = false;
        line.uiState.revolutLocalOutcome = result.local_outcome || false;
    }

    cancel(order, line) {
        const owner = this.owner(order, line);
        if (owner.cancellation) {
            return owner.cancellation;
        }
        let cancellation;
        if (owner.request && line.uiState.revolutDiscovering) {
            // Stop this read-only discovery before it can dispatch. Share its
            // result so cancellation cannot race a second lookup against it.
            owner.cancelDiscovery = true;
            cancellation = owner.request.then(() => this.cancelDiscovered(owner));
        } else {
            cancellation = this.cancelDiscovered(owner);
        }
        owner.cancellation = cancellation;
        cancellation.finally(() => {
            if (owner.cancellation === cancellation) {
                owner.cancellation = null;
            }
        });
        return cancellation;
    }

    async cancelDiscovered({ order, line }) {
        if (line.uiState.revolutUndispatched && !financialStartMayHaveOccurred(line)) {
            return true;
        }
        if (isRevolutRefund(line)) {
            this.showError(line, "unresolved");
            return false;
        }
        return this.cancelPayment({ order, line });
    }

    async cancelPayment({ order, line }) {
        const deadline = this.clock.now() + PAYMENT_TIMEOUT_MS;
        try {
            if (line.uiState.revolutStarting) {
                this.showError(line, "unresolved");
                return false;
            }
            if (!line.uiState.revolutOperationId) {
                const result = await this.clock.before(this.adapter.call("revolut_find_payment", [
                    [this.methodId], order.uuid, line.uuid,
                ]), deadline);
                if (!result || result.operation_id === line.uiState.revolutPreviousOperationId) {
                    this.showError(line, "interrupted");
                    return false;
                }
                this.remember(line, result);
            }
            this.remember(line, await this.clock.before(
                this.operationCall("revolut_cancel_payment", order, line), deadline
            ));
            const result = line.uiState.revolutSnapshot;
            if (result.state === "verified") {
                await this.adapter.setVerified(line, result);
                line.setPaymentStatus("done");
                return false;
            }
            this.showError(line, result.provider_state === "processing" ? "processing" :
                result.local_outcome || result.state);
            return result.retry_safe === true;
        } catch (error) {
            if (line.uiState.revolutSnapshot?.state === "verified") {
                await this.adapter.setVerified(line, line.uiState.revolutSnapshot);
                line.setPaymentStatus("done");
                return false;
            }
            this.showError(line, error instanceof ForegroundTimeout ? "timed_out" : "interrupted");
            return false;
        }
    }

    showError(line, outcome) {
        if (line.uiState.revolutSnapshot?.state === "verified") {
            return;
        }
        if (["interrupted", "timed_out"].includes(outcome)) {
            line.uiState.revolutLocalOutcome = outcome;
        }
        const providerState = line.uiState.revolutSnapshot?.provider_state;
        const state = outcome === "failed" &&
            TERMINAL_FAILURE_STATES.has(providerState)
            ? providerState : outcome;
        const messageKey = `${line.uiState.revolutOperationId}:${state}`;
        if (line.uiState.revolutMessage !== messageKey) {
            line.uiState.revolutMessage = messageKey;
            this.adapter.showError(line, state);
        }
    }
}
