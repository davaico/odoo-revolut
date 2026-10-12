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
            blocksAlternativeTender: false, hasExposure: false, retrySafe: false, canResume: false,
            shouldCancelBeforeDelete: false,
        };
    }
    const state = line.uiState || {};
    const refund = isRevolutRefund(line);
    const refundStarted = refund && financialStartMayHaveOccurred(line);
    const unstartedRefund = refund && !refundStarted;
    const failedRefund = refund && state.revolutSnapshot?.state === "failed";
    const awaitingCheckout = state.revolutSnapshot?.state === "verified" &&
        state.revolutCheckoutRestored !== true;
    const locked = state.revolutDiscovering ||
        (!unstartedRefund && !failedRefund && !state.revolutSelectingAllocation &&
        !state.revolutSnapshot?.retry_safe &&
        (financialStartMayHaveOccurred(line) ||
            (state.revolutUndispatched !== true && line.getPaymentStatus() === "waiting")));
    const reconcile = (state.revolutDiscovering || !unstartedRefund) &&
        !failedRefund && (locked || refund) &&
        state.revolutSnapshot?.state !== "verified";
    const retrySafe = !state.revolutDiscovering && !state.revolutRecoveredRetired &&
        (state.revolutSnapshot?.retry_safe === true ||
            (state.revolutUndispatched === true && !financialStartMayHaveOccurred(line)));
    return {
        canEditAmount: !locked && !failedRefund,
        canDelete: !locked,
        shouldCancelBeforeDelete: locked && state.revolutSnapshot?.state !== "verified",
        blocksCheckout: reconcile || failedRefund || awaitingCheckout,
        blocksAlternativeTender: reconcile || awaitingCheckout,
        hasExposure: locked || state.revolutStarting || Boolean(line.transaction_id) ||
            line.getPaymentStatus() === "done",
        refundException: (!state.revolutDiscovering && unstartedRefund) || failedRefund,
        retrySafe,
        canResume: retrySafe &&
            ["terminal_busy", "snapshot_invalid", "authority_required", "unstarted_recovered"].includes(state.revolutStartRejected),
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
        return line.uiState.revolutCheckoutRestored === true ? "verified" : "checkout_restore_failed";
    }
    if (isRevolutRefund(line)) {
        return line.uiState?.revolutLocalOutcome || snapshot?.local_outcome || snapshot?.state;
    }
    return TERMINAL_FAILURE_STATES.has(snapshot?.provider_state)
        ? snapshot.provider_state
        : line.uiState?.revolutLocalOutcome || snapshot?.local_outcome || snapshot?.state;
}

export function restorePaymentLine(line) {
    if (line.uiState.revolutRecoveredUnstarted || line.uiState.revolutRecoveredRetired) {
        // Recovery actions consume current server authority. A restored or
        // merged browser snapshot cannot know whether another cashier started.
        line.uiState.revolutRecoveredUnstarted = false;
        line.uiState.revolutRecoveredRetired = false;
        line.uiState.revolutUndispatched = false;
        line.uiState.revolutStarted = true;
        line.uiState.revolutStartRejected = false;
        line.uiState.revolutLocalOutcome = false;
    }
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
        (line.getPaymentStatus() !== "done" ||
            (line.uiState.revolutSnapshot?.state === "verified" &&
                line.uiState.revolutCheckoutRestored !== true))) {
        line.setPaymentStatus("retry");
    }
    restoreRefundTarget(line);
}

function restoreRefundTarget(line) {
    const result = line.uiState.revolutSnapshot;
    if (isRevolutRefund(line) && result?.state === "verified" &&
        Number.isSafeInteger(result.return_total_minor) && result.return_total_minor > 0) {
        // Use the server-checked total even before native draft sync. Native
        // cash rounding can differ; settlement still validates the return.
        line.pos_order_id.revolut_payable_target = -result.return_total_minor /
            10 ** line.pos_order_id.currency.decimal_places;
        line.pos_order_id.revolut_has_authority_exposure = true;
    }
}

export function paymentResponseSuccessful(line, successful) {
    return isRevolut(line) ? line.uiState.revolutSnapshot?.state === "verified" &&
        line.uiState.revolutCheckoutRestored === true : successful;
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
        this.checkoutRestoreTimeoutMs = PAYMENT_TIMEOUT_MS;
        this.lines = new Map();
    }

    afterSync(order, line) {
        const owner = this.owner(order, line);
        // A draft response can carry the waiting status serialized before the
        // latest provider observation. Idle recovery uses surviving evidence.
        if (!owner.request && !owner.cancellation && !owner.screenRequest && !owner.removal) {
            restorePaymentLine(line);
            if (paymentResponseSuccessful(line, true)) {
                line.setPaymentStatus("done");
            }
        }
    }

    async restore(order, line) {
        restorePaymentLine(line);
        if (!isRevolutRefund(line) || order.state !== "draft" ||
            !Number.isInteger(order.id) || !Number.isInteger(line.id)) {
            return;
        }
        try {
            // Recover committed evidence only. Startup never polls or starts
            // a refund; pending evidence leaves Check status available.
            const result = await this.clock.before(this.adapter.call("revolut_find_refund", [
                [this.methodId], order.uuid, line.uuid,
            ]), this.clock.now() + PAYMENT_TIMEOUT_MS);
            if (!result?.operation_id) {
                return;
            }
            this.remember(line, result);
            if (line.uiState.revolutSnapshot.state === "verified") {
                await this.setVerified(line);
                line.handlePaymentResponse(true);
            }
        } catch {
            // Offline or unauthorized reads cannot establish absence or
            // unlock a saved waiting line or its surviving references.
        } finally {
            restorePaymentLine(line);
        }
    }

    async setVerified(line) {
        const owner = this.owner(line.pos_order_id, line);
        if (owner.restoration) {
            return owner.restoration;
        }
        if (line.uiState.revolutCheckoutRestored === true) {
            return true;
        }
        const restore = async () => {
            let active = true;
            line.uiState.revolutRestoringCheckout = true;
            try {
                await this.clock.before(this.adapter.setVerified(line, line.uiState.revolutSnapshot,
                    { isCurrent: () => active }), this.clock.now() + this.checkoutRestoreTimeoutMs);
                // A native order refresh can replace the locally displayed target.
                restoreRefundTarget(line);
                line.uiState.revolutCheckoutRestored = true;
                line.uiState.revolutLocalOutcome = false;
                return true;
            } catch {
                // Financial evidence is final. Only canonical browser data is
                // missing; Check status must never send another financial request.
                line.uiState.revolutCheckoutRestored = false;
                line.uiState.revolutLocalOutcome = "checkout_restore_failed";
                line.setPaymentStatus("retry");
                this.adapter.showError(line, "checkout_restore_failed");
                return false;
            } finally {
                active = false;
                line.uiState.revolutRestoringCheckout = false;
            }
        };
        owner.restoration = restore().finally(() => { owner.restoration = null; });
        return owner.restoration;
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
        line.uiState.revolutMessage = false;
        owner.checkOnly = checkOnly;
        const request = Promise.resolve().then(invoke).finally(() => {
            if (owner.screenRequest === request) {
                owner.screenRequest = null;
                owner.checkOnly = false;
            }
        });
        owner.screenRequest = request;
        return request;
    }

    async screenCancel(order, line, resume, terminalIdle) {
        const owner = this.owner(order, line);
        if (paymentResponseSuccessful(line, true) && line.getPaymentStatus() === "done") {
            return false;
        }
        const screenRequest = owner.screenRequest;
        line.setPaymentStatus("waitingCancel");
        const safe = await this.cancel(order, line);
        if (line.uiState.revolutSnapshot?.state === "verified") {
            line.setPaymentStatus(paymentResponseSuccessful(line, true) ? "done" : "retry");
            if (!screenRequest && !owner.screenRequest && paymentResponseSuccessful(line, true)) {
                await resume();
            } else if (!owner.screenRequest) {
                terminalIdle();
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
        if (owner.removal) {
            return owner.removal.then(() => false);
        }
        if (owner.request) {
            return owner.request;
        }
        const request = this.waitForResult(owner, checkOnly || owner.checkOnly).finally(() => {
            if (owner.request === request) {
                owner.request = null;
                owner.line.setPaymentStatus(paymentResponseSuccessful(owner.line, true) ? "done" : "retry");
            }
        });
        owner.request = request;
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
            if (line.uiState.revolutRecoveredRetired && !checkOnly) {
                this.showError(line, "retired_recovered");
                return false;
            }
            if (line.uiState.revolutSnapshot?.state === "verified") {
                line.uiState.revolutDiscovering = false;
                return await this.setVerified(line);
            }
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
                    [[this.methodId], order.uuid, line.uuid, ...(!refund ? [this.sessionId] : [])]
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
                    return await this.setVerified(line);
                }
                if (!started && !result) {
                    line.uiState.revolutLocalOutcome = "discovery_cancelled";
                }
                return false;
            }
            if (!result && started) {
                // Refund reservations commit before any Merchant request. An
                // empty lookup alone is not proof: confirm absence under the
                // same order lock used by the reservation before unlocking.
                if (refund && !line.uiState.revolutOperationId &&
                    !line.transaction_id && !line.payment_ref_no) {
                    const proof = await this.clock.before(this.adapter.call(
                        "revolut_confirm_refund_absence", [[this.methodId], order.uuid, line.uuid, this.sessionId]
                    ), deadline);
                    if (proof?.operation_id) {
                        result = proof;
                        discovered = true;
                        this.remember(line, result);
                    } else if (proof?.dispatched === false &&
                        proof.start_rejected === "no_refund_attempt" &&
                        proof.order_uuid === order.uuid && proof.payment_line_uuid === line.uuid &&
                        !line.uiState.revolutOperationId && !line.uiState.revolutSnapshot &&
                        !line.transaction_id && !line.payment_ref_no) {
                        line.uiState.revolutOriginalOperationId = false;
                        line.uiState.revolutStarted = false;
                        line.uiState.revolutUndispatched = true;
                        line.uiState.revolutLocalOutcome = "no_refund_attempt";
                        line.setPaymentStatus("retry");
                        this.showError(line, "no_refund_attempt");
                        return false;
                    }
                }
                if (!refund && !result && this.canRecoverPayment(order, line)) {
                    result = await this.recoverPayment(order, line, deadline);
                    if (line.uiState.revolutRecoveredUnstarted || line.uiState.revolutRecoveredRetired) {
                        // Recovery changes admission authority, never starts a charge.
                        return false;
                    }
                    if (result?.operation_id) {
                        // Classification found a winning start. Retain its
                        // exposure; this recovery click sends no Merchant call.
                        if (result.state === "verified") {
                            return await this.setVerified(line);
                        }
                        this.showError(line, result.local_outcome || result.state);
                        return false;
                    }
                }
                if (!result) {
                    // A lost start response cannot prove that dispatch did not occur.
                    this.showError(line, "interrupted");
                    return false;
                }
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
                    line.uiState.revolutDiscovering = true;
                    try {
                        await this.clock.before(this.adapter.prepareRefund(order, line), deadline);
                    } catch (error) {
                        // A saved return is required before financial dispatch.
                        // Selection or a failed draft save is not a refund attempt.
                        line.uiState.revolutStarted = false;
                        line.uiState.revolutUndispatched = true;
                        line.uiState.revolutDiscovering = false;
                        line.uiState.revolutStartRejected = "snapshot_invalid";
                        line.uiState.revolutLocalOutcome = "snapshot_invalid";
                        line.uiState.revolutRejectionMessage = error?.data?.message || error.message;
                        this.showError(line, "snapshot_invalid");
                        return false;
                    }
                    if (owner.cancelDiscovery) {
                        return false;
                    }
                    line.uiState.revolutDiscovering = false;
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
                            line.uiState.revolutStarted = error.revolutRecoveryRequired === true;
                            line.uiState.revolutUndispatched = error.revolutRecoveryRequired !== true;
                        }
                        const outcome = error?.data?.name === "odoo.exceptions.AccessError"
                            ? "register_access_denied" : error.revolutRecoveryRequired === true
                                ? "recovery_required" : "authority_required";
                        line.uiState.revolutStartRejected = outcome;
                        line.uiState.revolutLocalOutcome = outcome;
                        line.uiState.revolutRejectionMessage = error?.data?.message || error.message;
                        this.showError(line, outcome);
                        return false;
                    }
                    // Saving and authorizing a draft is still preparation.
                    // Settle before dispatch so cancellation can await this
                    // request without the request awaiting cancellation.
                    if (owner.cancelDiscovery) {
                        if (!previousSnapshot) {
                            line.uiState.revolutLocalOutcome = "discovery_cancelled";
                        }
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
                    return await this.setVerified(line);
                }
                const deferredObservation = !refund && result.state === "unresolved" &&
                    result.observation_deferred === true;
                if (FINAL_FAILURE_STATES.has(result.state) && !deferredObservation) {
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
                return await this.setVerified(line);
            }
            if (error?.data?.name === "odoo.exceptions.AccessError") {
                line.uiState.revolutLocalOutcome = "register_access_denied";
                line.uiState.revolutRejectionMessage = error.data.message;
                this.showError(line, "register_access_denied");
                return false;
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

    canRecoverPayment(order, line) {
        return !isRevolutRefund(line) && order.state === "draft" &&
            Number.isInteger(order.id) && Number.isInteger(line.id) &&
            !line.uiState.revolutStarting && !line.uiState.revolutOperationId &&
            !line.uiState.revolutSnapshot && !line.transaction_id && !line.payment_ref_no;
    }

    async recoverPayment(order, line, deadline) {
        // Existing local proof may be stale after another cashier starts.
        // Keep the line guarded while obtaining current serialized authority.
        line.uiState.revolutRecoveredUnstarted = false;
        line.uiState.revolutRecoveredRetired = false;
        line.uiState.revolutStarted = true;
        line.uiState.revolutUndispatched = false;
        const proof = await this.clock.before(this.adapter.recoverPayment(order, line), deadline);
        if (proof?.operation_id) {
            this.remember(line, proof);
            return proof;
        }
        if (["unstarted", "retired"].includes(proof?.recovery_status) && proof.dispatched === false &&
            proof.order_id === order.id && proof.order_uuid === order.uuid &&
            proof.payment_id === line.id && proof.payment_line_uuid === line.uuid &&
            Number.isSafeInteger(proof.recovery_revision) && proof.recovery_revision > 0 &&
            this.canRecoverPayment(order, line)) {
            line.uiState.revolutRecoveredUnstarted = proof.recovery_status === "unstarted";
            line.uiState.revolutRecoveredRetired = proof.recovery_status === "retired";
            line.uiState.revolutRecoveryRequired = true;
            line.uiState.revolutRecoveryRevision = proof.recovery_revision;
            line.uiState.revolutStarted = false;
            line.uiState.revolutUndispatched = true;
            line.uiState.revolutStartRejected = `${proof.recovery_status}_recovered`;
            line.uiState.revolutLocalOutcome = `${proof.recovery_status}_recovered`;
        }
        return false;
    }

    removeRecoveredPayment(order, line) {
        const owner = this.owner(order, line);
        if (owner.removal) {
            return owner.removal;
        }
        const remove = async () => {
            line.uiState.revolutMessage = false;
            line.uiState.revolutRecoveredUnstarted = false;
            line.uiState.revolutRecoveredRetired = false;
            line.uiState.revolutStarted = true;
            line.uiState.revolutUndispatched = false;
            line.uiState.revolutDiscovering = true;
            try {
                const result = await this.clock.before(this.adapter.removeRecoveredPayment(order, line),
                    this.clock.now() + PAYMENT_TIMEOUT_MS);
                if (result?.operation_id) {
                    this.remember(line, result);
                    if (result.state === "verified") {
                        await this.setVerified(line);
                    } else {
                        this.showError(line, result.local_outcome || result.state);
                    }
                    return false;
                }
                if (result?.recovery_status !== "retired" || result.dispatched !== false ||
                    result.order_id !== order.id || result.order_uuid !== order.uuid ||
                    result.payment_id !== line.id || result.payment_line_uuid !== line.uuid ||
                    !Number.isSafeInteger(result.recovery_revision) || result.recovery_revision <= 0) {
                    this.showError(line, "interrupted");
                    return false;
                }
                line.uiState.revolutStarted = false;
                line.uiState.revolutUndispatched = true;
                line.uiState.revolutRecoveryRequired = false;
                line.uiState.revolutRetiredPayment = { orderId: result.order_id, paymentId: result.payment_id };
                return true;
            } catch (error) {
                this.showError(line, error instanceof ForegroundTimeout ? "timed_out" : "interrupted");
                return false;
            } finally {
                line.uiState.revolutDiscovering = false;
                line.setPaymentStatus(paymentResponseSuccessful(line, true) ? "done" : "retry");
            }
        };
        const removal = remove().finally(() => {
            if (owner.removal === removal) {
                owner.removal = null;
            }
        });
        owner.removal = removal;
        return removal;
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
        line.uiState.revolutRecoveredUnstarted = false;
        line.uiState.revolutRecoveredRetired = false;
        line.uiState.revolutRecoveryRequired = false;
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
        if (owner.removal) {
            return owner.removal;
        }
        if (owner.cancellation) {
            return owner.cancellation;
        }
        line.uiState.revolutMessage = false;
        let cancellation;
        if (owner.request && line.uiState.revolutDiscovering) {
            // Stop discovery/preparation before it can dispatch. Share its
            // result so cancellation cannot race a second lookup against it.
            owner.cancelDiscovery = true;
            cancellation = owner.request.then(() => {
                // Cancelling preparation of a retry leaves the already-final
                // prior attempt intact; no new attempt needs cancellation.
                if (!isRevolutRefund(line) && line.uiState.revolutSnapshot?.retry_safe === true) {
                    return true;
                }
                return this.cancelDiscovered(owner);
            });
        } else {
            cancellation = this.cancelDiscovered(owner);
        }
        const request = cancellation.finally(() => {
            if (owner.cancellation === request) {
                owner.cancellation = null;
            }
        });
        owner.cancellation = request;
        return request;
    }

    async cancelDiscovered({ order, line }) {
        if (line.uiState.revolutSnapshot?.state === "verified") {
            await this.setVerified(line);
            return false;
        }
        if (line.uiState.revolutUndispatched && !financialStartMayHaveOccurred(line) &&
            !line.uiState.revolutRecoveryRequired) {
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
                if (!result && this.canRecoverPayment(order, line)) {
                    const recovered = await this.recoverPayment(order, line, deadline);
                    if (line.uiState.revolutRecoveredUnstarted || line.uiState.revolutRecoveredRetired) {
                        return true;
                    }
                    if (recovered?.operation_id) {
                        // Recovery reports the winning start without cancelling
                        // it. A subsequent explicit action may reconcile it.
                        if (recovered.state === "verified") {
                            await this.setVerified(line);
                        } else {
                            this.showError(line, recovered.local_outcome || recovered.state);
                        }
                        return false;
                    }
                } else if (result?.operation_id) {
                    this.remember(line, result);
                }
                if (!line.uiState.revolutOperationId ||
                    line.uiState.revolutOperationId === line.uiState.revolutPreviousOperationId) {
                    this.showError(line, "interrupted");
                    return false;
                }
            }
            let result;
            while (true) {
                if (this.clock.now() >= deadline) {
                    throw new ForegroundTimeout();
                }
                this.remember(line, await this.clock.before(
                    this.operationCall("revolut_cancel_payment", order, line), deadline
                ));
                result = line.uiState.revolutSnapshot;
                if (result.state === "verified" || result.retry_safe === true ||
                    result.observation_deferred !== true) {
                    break;
                }
                // A concurrent observer or server cadence can defer Cancel
                // before it acts. Keep this click pending; the server owns
                // the one-time cancellation dispatch and its reconciliation.
                await this.clock.before(this.clock.wait(POLL_INTERVAL_MS), deadline);
                result = line.uiState.revolutSnapshot;
                if (result.state === "verified" || result.retry_safe === true) {
                    break;
                }
            }
            if (result.state === "verified") {
                if (await this.setVerified(line)) {
                    line.setPaymentStatus("done");
                }
                return false;
            }
            this.showError(line, result.provider_state === "processing" ? "processing" :
                result.local_outcome || result.state);
            return result.retry_safe === true;
        } catch (error) {
            if (line.uiState.revolutSnapshot?.state === "verified") {
                if (await this.setVerified(line)) {
                    line.setPaymentStatus("done");
                }
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
