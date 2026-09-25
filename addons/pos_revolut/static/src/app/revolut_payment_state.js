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

function refundMayHaveStarted(line) {
    const state = line.uiState || {};
    return Boolean(state.revolutStarted || state.revolutStarting ||
        state.revolutOperationId || state.revolutSnapshot ||
        state.revolutOriginalOperationId || line.transaction_id || line.payment_ref_no);
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
    const refundStarted = refund && refundMayHaveStarted(line);
    const unstartedRefund = refund && !refundStarted;
    const failedRefund = refund && state.revolutSnapshot?.state === "failed";
    const locked = !unstartedRefund && !failedRefund && !state.revolutSelectingAllocation &&
        !state.revolutSnapshot?.retry_safe &&
        (refundStarted || state.revolutStarted ||
            ["retry", "waiting", "waitingCard", "waitingCancel"].includes(line.getPaymentStatus()));
    const reconcile = !unstartedRefund && !failedRefund && (locked || refund) &&
        state.revolutSnapshot?.state !== "verified";
    return {
        canEditAmount: !locked && !failedRefund,
        canDelete: !locked,
        shouldCancelBeforeDelete: locked && state.revolutSnapshot?.state !== "verified",
        blocksCheckout: reconcile || failedRefund,
        blocksAlternativeTender: reconcile,
        hasExposure: locked || state.revolutStarting || Boolean(line.transaction_id) ||
            line.getPaymentStatus() === "done",
        refundException: unstartedRefund || failedRefund,
        retrySafe: state.revolutSnapshot?.retry_safe === true,
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
    line.uiState.revolutStarting = false;
    if (isRevolut(line) && line.uiState.revolutStarted && line.getPaymentStatus() !== "done") {
        line.setPaymentStatus("retry");
    }
}

export function paymentResponseSuccessful(line, successful) {
    return isRevolut(line) && line.uiState.revolutSnapshot?.state === "verified" ? true : successful;
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

    screenRequest(order, line, invoke) {
        const owner = this.owner(order, line);
        if (owner.screenRequest) {
            return owner.screenRequest;
        }
        const request = Promise.resolve().then(invoke);
        owner.screenRequest = request;
        return request.finally(() => {
            if (owner.screenRequest === request) {
                owner.screenRequest = null;
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

    request(order, line) {
        const owner = this.owner(order, line);
        if (owner.request) {
            return owner.request;
        }
        const request = this.waitForResult(owner);
        owner.request = request;
        request.finally(() => {
            if (owner.request === request) {
                owner.request = null;
            }
        });
        return request;
    }

    async waitForResult(owner) {
        const { order, line } = owner;
        const refund = isRevolutRefund(line);
        const pollMethod = refund ? "revolut_poll_refund" : "revolut_poll_payment";
        const started = refund ? refundMayHaveStarted(line) : line.uiState.revolutStarted;
        let deadline = this.clock.now() + PAYMENT_TIMEOUT_MS;
        line.uiState.revolutStarted = true;
        line.setPaymentStatus("waiting");
        try {
            if (refund) {
                try {
                    await this.clock.before(this.adapter.restoreRefundOriginals(order), deadline);
                } catch (error) {
                    if (started) {
                        throw error;
                    }
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
            if (!result && started) {
                // A lost start response cannot prove that dispatch did not occur.
                this.showError(line, "interrupted");
                return false;
            }
            if (!result || (!refund && result.retry_safe && !discovered)) {
                const previousOperationId = result?.retry_safe ? result.operation_id : false;
                let originalOperationId = false;
                if (refund) {
                    line.uiState.revolutOperationId = false;
                    let sources;
                    try {
                        sources = await this.clock.before(this.adapter.call("revolut_refund_sources", [
                            [this.methodId], this.sessionId, this.currencyId,
                            this.adapter.financialSnapshot(order),
                        ]), deadline);
                    } catch {
                        this.adapter.discardRefund(line);
                        this.adapter.showPreparationError(line, "sources");
                        return false;
                    }
                    if (!Array.isArray(sources) || !sources.length) {
                        this.adapter.discardRefund(line);
                        this.adapter.showPreparationError(line, "balance");
                        return false;
                    }
                    const allocation = await this.adapter.chooseAllocation(sources, line);
                    if (!allocation) {
                        this.adapter.discardRefund(line);
                        return false;
                    }
                    originalOperationId = allocation.operationId;
                    deadline = this.clock.now() + PAYMENT_TIMEOUT_MS;
                    this.adapter.setRefundAmount(line, allocation.amount);
                    line.uiState.revolutOriginalOperationId = originalOperationId;
                }
                line.uiState.revolutPreviousOperationId = previousOperationId;
                line.uiState.revolutSnapshot = false;
                line.uiState.revolutOperationId = false;
                line.uiState.revolutStarting = true;
                try {
                    result = await this.clock.before(this.adapter.call(
                        refund ? "revolut_start_refund" : "revolut_start_payment",
                        [[this.methodId], this.sessionId, order.uuid, line.uuid,
                            line.amount, this.currencyId,
                            ...(!refund ? [previousOperationId] : []),
                            this.adapter.financialSnapshot(order),
                            ...(refund ? [originalOperationId] : [])]
                    ), deadline);
                } finally {
                    line.uiState.revolutStarting = false;
                }
            } else if (!result?.operation_id) {
                this.showError(line, "interrupted");
                return false;
            } else if (result.state !== "verified" && !result.retry_safe) {
                line.uiState.revolutOperationId = result.operation_id;
                result = await this.clock.before(this.operationCall(pollMethod, order, line), deadline);
            }
            this.remember(line, result);
            while (this.clock.now() < deadline) {
                if (owner.cancellation) {
                    await this.clock.before(owner.cancellation, deadline);
                }
                result = line.uiState.revolutSnapshot;
                if (result.state === "verified") {
                    this.adapter.setVerified(line, result);
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
                this.adapter.setVerified(line, line.uiState.revolutSnapshot);
                return true;
            }
            const outcome = error instanceof ForegroundTimeout ? "timed_out" : "interrupted";
            line.uiState.revolutLocalOutcome = outcome;
            if (outcome === "timed_out" && line.uiState.revolutOperationId) {
                this.operationCall(refund ? "revolut_mark_refund_timeout" : "revolut_mark_timeout", order, line)
                    .catch(() => {});
            }
            this.showError(line, outcome);
            return false;
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
        line.uiState.revolutLocalOutcome = result.local_outcome || false;
    }

    cancel(order, line) {
        const owner = this.owner(order, line);
        if (isRevolutRefund(line)) {
            this.showError(line, "unresolved");
            return Promise.resolve(false);
        }
        if (owner.cancellation) {
            return owner.cancellation;
        }
        const cancellation = this.cancelPayment(owner);
        owner.cancellation = cancellation;
        cancellation.finally(() => {
            if (owner.cancellation === cancellation) {
                owner.cancellation = null;
            }
        });
        return cancellation;
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
                this.adapter.setVerified(line, result);
                line.setPaymentStatus("done");
                return false;
            }
            this.showError(line, result.provider_state === "processing" ? "processing" :
                result.local_outcome || result.state);
            return result.retry_safe === true;
        } catch (error) {
            if (line.uiState.revolutSnapshot?.state === "verified") {
                this.adapter.setVerified(line, line.uiState.revolutSnapshot);
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
