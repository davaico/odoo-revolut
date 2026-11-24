"""Apply native register visibility to the manager's financial worklists.

Related-record rules are not applied automatically by an ir.rule domain on a
financial model. Keep the entitlement rules in XML and intersect searches and
direct reads with fresh native config/session/order queries. Query objects stay
lazy; no user's changing register allowlist is cached in a rule expression.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from odoo import models
from odoo.exceptions import AccessError
from odoo.osv.expression import AND, OR, expression
from odoo.tools import Query, SQL


_OPERATION_NATIVE_PATHS = (
    ("operation_id.pos_config_id", "pos.config", False),
    ("operation_id.pos_session_id", "pos.session", False),
    ("operation_id.pos_order_id", "pos.order", True),
    ("operation_id.authorization_id.pos_order_id", "pos.order", True),
)

_rule_cursor = ContextVar("revolut_register_rule_cursor", default=None)


@contextmanager
def _compiling_register_rules(cursor):
    token = _rule_cursor.set(cursor)
    try:
        yield
    finally:
        _rule_cursor.reset(token)


class RevolutRegisterWorklistMixin(models.AbstractModel):
    _name = "pos.revolut.register.worklist.mixin"
    _description = "Native register visibility for Revolut financial worklists"

    _revolut_register_paths = ()
    _revolut_order_identity_paths = ()

    def _revolut_native_visibility_domain(self):
        domain = []
        for path, model, optional in self._revolut_register_paths:
            query = self.env[model].with_context(active_test=False)._search([])
            accessible = [(path, "in", query)]
            if optional:
                # A missing intermediate many2one does not necessarily match
                # a dotted '= False' condition: its join may require a parent.
                # Legacy operations legitimately have no cart authority yet.
                names = path.split(".")
                accessible = OR([accessible, OR([
                    [(".".join(names[:length]), "=", False)]
                    for length in range(1, len(names) + 1)
                ])])
            domain = AND([domain, accessible])
        for prefix in self._revolut_order_identity_paths:
            owner = self.browse().mapped(prefix[:-1]) if prefix else self
            visible = owner._revolut_visible_order_identities()
            domain = AND([domain, [(prefix + "id", "in", visible)]])
        return domain

    def _revolut_visible_order_identities(self):
        """Include legacy attempts only if their matching native draft is readable."""
        orders = self.env["pos.order"].with_context(active_test=False)
        all_orders = orders.sudo()
        existing = all_orders._search([
            ("company_id", "in", self.env.companies.ids), ("uuid", "!=", False),
        ])
        readable = orders._search([])
        owner = self.sudo()
        owners = owner._where_calc([], active_test=False)
        owner_uuid = owner._field_to_sql(owners.table, "order_uuid", owners)
        owner_company = owner._field_to_sql(owners.table, "company_id", owners)
        candidate_fields = [all_orders._field_to_sql(existing.table, name, existing)
                            for name in ("id", "company_id", "uuid")]
        hidden = SQL(
            """SELECT candidate.uuid FROM %s AS candidate
                WHERE candidate.company_id = %s
                  AND NOT EXISTS (SELECT 1 FROM %s AS readable WHERE readable.id = candidate.id)""",
            existing.subselect(*candidate_fields),
            owner_company, readable.subselect(SQL.identifier(readable.table, "id")),
        )
        visible = SQL("NOT EXISTS (%s AND candidate.uuid = %s)", hidden, owner_uuid)
        if not self._fields["order_uuid"].required:
            # Preserve the previous NOT IN behavior for an unassociated refund:
            # NULL passes only when the set of hidden UUIDs is empty.
            visible = SQL("CASE WHEN %s IS NULL THEN NOT EXISTS (%s) ELSE %s END",
                          owner_uuid, hidden, visible)
        owners.add_where(visible)
        return owners

    def _condition_to_sql(self, alias, fname, operator, value, query):
        if (_rule_cursor.get() is self.env.cr and operator == "in"
                and isinstance(value, Query) and value._ids is None
                and fname in ("pos_order_id", "pos_session_id", "pos_config_id",
                              "authorization_id", "original_operation_id",
                              "revolut_operation_id", "revolut_refund_operation_id")):
            # Probe native visibility and grant queries with the current foreign
            # key. Leave known ID lists to the ORM and apply the correlation
            # outside the subquery so its LIMIT and OFFSET retain their meaning.
            related_id = self._field_to_sql(alias, fname, query)
            value = SQL(
                "(SELECT visible.id FROM %s AS visible WHERE visible.id = %s)",
                value.subselect(SQL.identifier(value.table, "id")), related_id,
            )
        return super()._condition_to_sql(alias, fname, operator, value, query)

    def _apply_ir_rules(self, query, mode="read"):
        if self.env.su or mode != "read":
            return super()._apply_ir_rules(query, mode)
        # The caller's search domain was already compiled by _where_calc.
        # Only scope access predicates; an ordinary search by order UUID
        # should still start from the matching order and join to its tenders.
        with _compiling_register_rules(self.env.cr):
            super()._apply_ir_rules(query, mode)
            expression(self._revolut_native_visibility_domain(), self, query=query)

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result or self.env.su or operation != "read" or not self:
            return result
        # Odoo 18's Python filtered_domain cannot evaluate Query/SQL values.
        # Evaluate the caller-derived visibility domain in SQL, with sudo only
        # for this final ID query; its native subqueries retain caller rules.
        with _compiling_register_rules(self.env.cr):
            accessible = self.sudo().with_context(active_test=False).search(AND([
                [("id", "in", self.ids)], self._revolut_native_visibility_domain(),
            ]))
        forbidden = self - accessible
        if forbidden:
            message = self.env._(
                "This Revolut record belongs to a register, session or order you cannot access."
            )
            return forbidden, lambda: AccessError(message)
        return None


class RevolutPaymentWorklist(models.Model):
    _name = "pos.revolut.payment.operation"
    _inherit = ["pos.revolut.payment.operation", "pos.revolut.register.worklist.mixin"]

    _revolut_register_paths = (
        ("pos_config_id", "pos.config", False),
        ("pos_session_id", "pos.session", False),
        ("pos_order_id", "pos.order", True),
        ("authorization_id.pos_order_id", "pos.order", True),
    )
    _revolut_order_identity_paths = ("",)


class RevolutRefundWorklist(models.Model):
    _name = "pos.revolut.refund.operation"
    _inherit = ["pos.revolut.refund.operation", "pos.revolut.register.worklist.mixin"]

    _revolut_register_paths = (
        ("original_operation_id.pos_config_id", "pos.config", False),
        ("original_operation_id.pos_session_id", "pos.session", False),
        ("original_operation_id.pos_order_id", "pos.order", True),
        ("original_operation_id.authorization_id.pos_order_id", "pos.order", True),
        ("pos_session_id.config_id", "pos.config", False),
        ("pos_session_id", "pos.session", False),
        ("pos_order_id", "pos.order", True),
    )
    _revolut_order_identity_paths = ("", "original_operation_id.")


class RevolutCartWorklist(models.Model):
    _name = "pos.revolut.cart.authorization"
    _inherit = ["pos.revolut.cart.authorization", "pos.revolut.register.worklist.mixin"]

    _revolut_register_paths = (
        ("config_id", "pos.config", False),
        ("session_id", "pos.session", False),
        ("pos_order_id", "pos.order", False),
    )
    _revolut_order_identity_paths = ("",)


class RevolutDispatchWorklist(models.Model):
    _name = "pos.revolut.payment.dispatch"
    _inherit = ["pos.revolut.payment.dispatch", "pos.revolut.register.worklist.mixin"]

    _revolut_register_paths = _OPERATION_NATIVE_PATHS
    _revolut_order_identity_paths = ("operation_id.",)


class RevolutAuditWorklist(models.Model):
    _name = "pos.revolut.reconciliation.audit"
    _inherit = ["pos.revolut.reconciliation.audit", "pos.revolut.register.worklist.mixin"]

    _revolut_register_paths = _OPERATION_NATIVE_PATHS
    _revolut_order_identity_paths = ("operation_id.",)


class RevolutOrderLockWorklist(models.Model):
    _name = "pos.revolut.order.lock"
    _inherit = ["pos.revolut.order.lock", "pos.revolut.register.worklist.mixin"]

    def _revolut_native_visibility_domain(self):
        # Locks have only company/UUID identity. A visible persisted financial
        # record supplies register authority; orphan locks expose no evidence.
        # Compute this on every access, including after grant/rule revocation.
        uuids_by_company = {}
        for model in ("pos.revolut.payment.operation", "pos.revolut.refund.operation",
                      "pos.revolut.cart.authorization"):
            for record in self.env[model].search([]):
                uuids_by_company.setdefault(record.company_id.id, set()).add(record.order_uuid)
        return OR([
            [("company_id", "=", company_id), ("order_uuid", "in", list(uuids))]
            for company_id, uuids in uuids_by_company.items()
        ])


class RevolutNativeTenderWorklist(models.Model):
    _name = "pos.payment"
    _inherit = ["pos.payment", "pos.revolut.register.worklist.mixin"]

    _revolut_register_paths = (
        ("pos_order_id.config_id", "pos.config", False),
        ("pos_order_id.session_id", "pos.session", False),
        ("pos_order_id", "pos.order", False),
    )

    def _revolut_native_visibility_domain(self):
        ordinary = [
            ("revolut_operation_id", "=", False),
            ("revolut_refund_operation_id", "=", False),
            ("payment_method_id.use_payment_terminal", "!=", "revolut"),
        ]
        protected = super()._revolut_native_visibility_domain()
        granted = self.env["pos.config"].sudo()._search(
            [("revolut_user_ids", "in", [self.env.uid])]
        )
        # Cashiers have no general financial-model ACL. Build caller-native
        # identity constraints first, then use sudo only for the ID subqueries.
        # Frozen sessions/grants stay authoritative after order rollover.
        for relation, model, paths in (
            ("revolut_operation_id", "pos.revolut.payment.operation", ("pos_config_id",)),
            ("revolut_refund_operation_id", "pos.revolut.refund.operation",
             ("original_operation_id.pos_config_id", "pos_session_id.config_id")),
        ):
            operations = self.env[model]
            visible = operations._revolut_native_visibility_domain()
            for path in paths:
                visible = AND([visible, [(path, "in", granted)]])
            query = operations.sudo()._search(visible)
            protected = AND([protected, OR([
                [(relation, "=", False)], [(relation, "in", query)],
            ])])
        return OR([ordinary, protected])
