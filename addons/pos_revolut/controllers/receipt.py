from markupsafe import escape

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request


class RevolutReceiptController(http.Controller):
    @http.route("/pos_revolut/receipt/<string:kind>/<int:operation_id>", type="http", auth="user", methods=["GET"], readonly=True)
    def download(self, kind, operation_id, **kwargs):
        try:
            request.env["pos.revolut.receipt"]._operation(kind, operation_id)
            report_ref = f"pos_revolut.action_report_revolut_{kind}_receipt"
            pdf, _format = request.env["ir.actions.report"].with_context(
                report_pdf_no_attachment=True, force_report_rendering=True,
            )._render_qweb_pdf(report_ref, [operation_id])
        except AccessError:
            return request.make_response(str(escape(_("This Revolut receipt is not accessible."))), status=403)
        except UserError as error:
            return request.make_response(str(escape(error.args[0])), status=409)
        except Exception:
            # Render failures cannot change the immutable financial operation.
            return request.make_response(str(escape(_("The receipt PDF could not be generated. Retry the download or contact a POS manager."))), status=503)
        return request.make_response(pdf, headers=[
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", content_disposition(f"revolut-{kind}-{operation_id}.pdf")),
            ("Cache-Control", "private, no-store"),
        ])
