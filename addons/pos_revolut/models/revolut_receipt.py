from decimal import Decimal

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class RevolutReceipt(models.AbstractModel):
    _name = "pos.revolut.receipt"
    _description = "Authorized Revolut Receipt Documents"

    @api.model
    def _check_order_access(self, orders):
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only Point of Sale staff can download Revolut receipts."))
        if not orders or not orders.exists():
            raise AccessError(_("The receipt sale is not accessible."))
        orders.check_access("read")
        allowed = set(self.env.companies.ids) & set(self.env.user.company_ids.ids)
        if any(order.company_id.id not in allowed for order in orders):
            raise AccessError(_("The receipt company is not active or accessible."))

    @api.model
    def _operation(self, kind, operation_id):
        if kind not in {"payment", "refund"} or type(operation_id) is not int:
            raise UserError(_("Select a valid Revolut payment or refund receipt."))
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only Point of Sale staff can download Revolut receipts."))
        allowed = set(self.env.companies.ids) & set(self.env.user.company_ids.ids)
        # Cashiers have no general access to financial operation records. Read
        # only ownership first, then authorize the sale before reading evidence.
        operation = self.env[f"pos.revolut.{kind}.operation"].sudo().search([
            ("id", "=", operation_id), ("company_id", "in", list(allowed)),
        ], limit=1)
        if not operation:
            raise AccessError(_("The Revolut receipt is not accessible."))
        order_ids = operation.pos_order_id.ids
        if kind == "refund":
            order_ids += operation.original_operation_id.pos_order_id.ids
        orders = self.env["pos.order"].browse(list(set(order_ids)))
        self._check_order_access(orders)
        if operation.state != "verified":
            raise UserError(_("A receipt is available only after Revolut verification succeeds."))
        source = operation if kind == "payment" else operation.original_operation_id
        if kind == "refund":
            self._operation("payment", source.id)
        currency_code = source.currency_code
        amount_minor = Decimal(str(operation.amount)) * (10 ** operation.currency_id.decimal_places)
        if (not operation.revolut_order_id or not currency_code
                or currency_code != operation.currency_id.name
                or operation.amount_minor <= 0 or amount_minor != operation.amount_minor
                or operation.company_id != source.company_id
                or operation.currency_id != source.currency_id
                or any(order.company_id != operation.company_id for order in orders)
                or (kind == "payment" and not operation.revolut_payment_id)
                or (kind == "refund" and (source.state != "verified"
                    or not source.revolut_payment_id or not source.revolut_order_id
                    or source.amount_minor <= 0
                    or operation.amount_minor > source.amount_minor))):
            raise UserError(_("Required verified receipt evidence is inconsistent. Contact a POS manager."))
        if operation.pos_order_id and (
            operation.pos_order_id.uuid != operation.order_uuid
            or operation.pos_order_id.currency_id != operation.currency_id
        ):
            raise UserError(_("The receipt sale does not match the verified operation. Contact a POS manager."))
        tender = operation.pos_payment_id
        if tender and (
            tender.pos_order_id != operation.pos_order_id
            or tender.company_id != operation.company_id
            or tender.uuid != operation.payment_line_uuid
            or tender.payment_method_id != operation.payment_method_id
            or operation.currency_id.compare_amounts(tender.amount, operation.amount if kind == "payment" else -operation.amount)
            or tender.transaction_id != (operation.revolut_payment_id if kind == "payment" else operation.revolut_order_id)
            or (kind == "payment" and tender.revolut_operation_id != operation)
            or (kind == "refund" and tender.revolut_refund_operation_id != operation)
        ):
            raise UserError(_("The receipt tender does not match the verified operation. Contact a POS manager."))
        return operation

    @api.model
    def _download_url(self, kind, operation_id):
        return f"/pos_revolut/receipt/{kind}/{operation_id}"

    @api.model
    def _document(self, kind, operation_id):
        operation = self._operation(kind, operation_id)
        source = operation if kind == "payment" else operation.original_operation_id
        merchant = operation.receipt_merchant_snapshot or operation._receipt_merchant_identity()
        sale = operation.pos_order_id or source.pos_order_id
        return {
            "kind": kind,
            "title": _("Odoo-generated Revolut payment receipt") if kind == "payment" else _("Odoo-generated Revolut refund receipt"),
            "operation_id": operation.id,
            "merchant": merchant,
            "merchant_label": _("Merchant identity recorded at verification") if operation.receipt_merchant_snapshot else _("Current merchant identity (historical identity not retained)"),
            "sale_reference": sale.name,
            "sale_uuid": operation.order_uuid,
            "amount": f"{operation.amount:.{operation.currency_id.decimal_places}f}",
            "currency": source.currency_code,
            "revolut_order_id": operation.revolut_order_id,
            "revolut_payment_id": source.revolut_payment_id if kind == "payment" else False,
            "verified_at": fields.Datetime.to_string(operation.verified_at) if operation.verified_at else False,
            "downloaded_at": fields.Datetime.to_string(fields.Datetime.now()),
            "original_sale_reference": source.pos_order_id.name if kind == "refund" else False,
            "original_order_id": source.revolut_order_id if kind == "refund" else False,
            "original_payment_id": source.revolut_payment_id if kind == "refund" else False,
        }


class RevolutPaymentReceiptReport(models.AbstractModel):
    _name = "report.pos_revolut.report_revolut_payment_receipt"
    _description = "Revolut Payment Receipt Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        return {"documents": [self.env["pos.revolut.receipt"]._document("payment", identifier) for identifier in docids]}


class RevolutRefundReceiptReport(models.AbstractModel):
    _name = "report.pos_revolut.report_revolut_refund_receipt"
    _description = "Revolut Refund Receipt Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        return {"documents": [self.env["pos.revolut.receipt"]._document("refund", identifier) for identifier in docids]}


class RevolutReceiptReportLayout(models.Model):
    _inherit = "ir.actions.report"

    def _get_layout(self):
        if len(self) == 1 and self.report_name in {
            "pos_revolut.report_revolut_payment_receipt",
            "pos_revolut.report_revolut_refund_receipt",
        }:
            # Receipt styling is self-contained: printing needs no live asset
            # HTTP requests or company branding that could rewrite history.
            return self.env.ref("pos_revolut.report_revolut_receipt_layout")
        return super()._get_layout()


class PosOrderReceipt(models.Model):
    _inherit = "pos.order"

    revolut_receipt_links = fields.Html(
        compute="_compute_revolut_receipt_links", sanitize=True,
        groups="point_of_sale.group_pos_user",
    )

    def revolut_receipt_options(self):
        self.ensure_one()
        receipts = self.env["pos.revolut.receipt"]
        receipts._check_order_access(self)
        payments = self.env["pos.revolut.payment.operation"].sudo().search([
            ("pos_order_id", "=", self.id), ("state", "=", "verified"),
        ], order="id")
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            "|", ("pos_order_id", "=", self.id),
            ("original_operation_id.pos_order_id", "=", self.id),
            ("state", "=", "verified"),
        ], order="id")
        options = []
        for kind, operations in (("payment", payments), ("refund", refunds)):
            for operation in operations:
                # An inconsistent verified record remains visible to staff;
                # the document endpoint supplies an actionable evidence error.
                receipts._check_order_access(self.env["pos.order"].browse(operation.pos_order_id.ids + (
                    operation.original_operation_id.pos_order_id.ids if kind == "refund" else []
                )))
                label = _("Payment") if kind == "payment" else _("Refund")
                options.append({"kind": kind, "operation_id": operation.id,
                    "label": f"{label} {operation.amount:.{operation.currency_id.decimal_places}f} {operation.currency_id.name} - {operation.revolut_order_id or operation.id}",
                    "url": receipts._download_url(kind, operation.id)})
        return options

    def _compute_revolut_receipt_links(self):
        for order in self:
            options = order.revolut_receipt_options() if order.id else []
            order.revolut_receipt_links = Markup("<ul>{}</ul>").format(Markup("").join(
                Markup('<li><a href="{}" target="_blank">{}</a></li>').format(option["url"], option["label"])
                for option in options
            )) if options else _("No verified Revolut receipts are available for this sale.")
