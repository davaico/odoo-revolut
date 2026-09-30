import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { downloadFile } from "@web/core/network/download";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

class RevolutReceiptSelection extends Component {
    static template = "pos_revolut.RevolutReceiptSelection";
    static components = { Dialog };
    static props = ["options", "onDownload", "close"];

    setup() {
        this.state = useState({ downloading: false });
    }

    get title() {
        return _t("Revolut receipts");
    }

    async download(option) {
        if (this.state.downloading) {
            return;
        }
        this.state.downloading = `${option.kind}:${option.operation_id}`;
        try {
            await this.props.onDownload(option);
        } finally {
            this.state.downloading = false;
        }
    }
}

class RevolutReceiptButton extends Component {
    static template = "pos_revolut.RevolutReceiptButton";
    static props = { order: { optional: true } };

    setup() {
        this.pos = usePos();
        this.dialog = useService("dialog");
        this.state = useState({ options: [], loading: false, downloading: false, error: false });
        this.requestNumber = 0;
        onWillStart(() => this.loadOptions(this.props.order));
        onWillUpdateProps((props) => {
            if (props.order?.id !== this.props.order?.id) {
                return this.loadOptions(props.order);
            }
        });
    }

    async loadOptions(order) {
        const requestNumber = ++this.requestNumber;
        this.state.options = [];
        this.state.error = false;
        this.state.loading = false;
        if (!Number.isInteger(order?.id)) {
            return;
        }
        this.state.loading = true;
        try {
            const options = await this.pos.data.call("pos.order", "revolut_receipt_options", [[order.id]]);
            if (requestNumber === this.requestNumber) {
                this.state.options = options;
            }
        } catch {
            if (requestNumber === this.requestNumber) {
                this.state.error = true;
            }
        } finally {
            if (requestNumber === this.requestNumber) {
                this.state.loading = false;
            }
        }
    }

    async open() {
        if (this.state.loading || this.state.downloading) {
            return;
        }
        await this.loadOptions(this.props.order);
        if (this.state.error) {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut receipts unavailable"),
                body: _t("Could not load the available receipts. Check your connection and active company, then try again."),
            });
        } else if (this.state.options.length === 1) {
            await this.download(this.state.options[0]);
        } else if (this.state.options.length > 1) {
            this.dialog.add(RevolutReceiptSelection, {
                options: this.state.options,
                onDownload: (option) => this.download(option),
            });
        } else {
            this.dialog.add(AlertDialog, {
                title: _t("No completed Revolut receipt"),
                body: _t("There is no verified Revolut payment or refund receipt available for this order. Ask a POS manager to review its payment evidence."),
            });
        }
    }

    async download(option) {
        this.state.downloading = true;
        try {
            await downloadFile(option.url);
        } catch {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut receipt download failed"),
                body: _t("The PDF could not be generated or downloaded. Check your connection and active company, then retry. If it still fails, ask a POS manager to check the receipt evidence and report configuration. The payment or refund outcome has not changed."),
            });
        } finally {
            this.state.downloading = false;
        }
    }
}

patch(ReceiptScreen, {
    components: { ...ReceiptScreen.components, RevolutReceiptButton },
});
patch(TicketScreen, {
    components: { ...TicketScreen.components, RevolutReceiptButton },
});
