"""Server cart authority and tender admission share the durable order boundary."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import timedelta
from decimal import Decimal, DecimalException
from hashlib import sha256
import json
from uuid import UUID, uuid5, NAMESPACE_URL

from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure

from odoo import _, api, fields, models, Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_round

from .financial_snapshot import check_line_count_size

_authority_cursor = ContextVar('revolut_authority_cursor', default=None)


@contextmanager
def _authority_mutation(env):
    token = _authority_cursor.set(env.cr)
    try:
        yield
    finally:
        _authority_cursor.reset(token)


def _authority_internal(env):
    return _authority_cursor.get() is env.cr


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _tender_amount(currency, value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)) or len(str(value)) > 64:
        raise UserError(currency.env._('The tender amount is invalid.'))
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or not -64 <= amount.as_tuple().exponent <= 64:
            raise ValueError()
        minor = amount * (10**currency.decimal_places)
        if not amount.is_finite() or abs(minor) > 2147483647 or minor != minor.to_integral_value():
            raise ValueError()
        return float(amount), int(minor)
    except (DecimalException, ValueError, OverflowError):
        raise UserError(currency.env._('Use a finite tender amount in exact currency minor units.')) from None


class RevolutCartAuthorization(models.Model):
    _name = 'pos.revolut.cart.authorization'
    _description = 'Immutable Revolut Base Cart Authorization'
    _order = 'id desc'

    pos_order_id = fields.Many2one('pos.order', readonly=True, ondelete='set null', index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, ondelete='restrict', index=True)
    session_id = fields.Many2one('pos.session', required=True, readonly=True, ondelete='restrict')
    config_id = fields.Many2one('pos.config', required=True, readonly=True, ondelete='restrict')
    currency_id = fields.Many2one('res.currency', required=True, readonly=True, ondelete='restrict')
    order_uuid = fields.Char(required=True, readonly=True)
    cart_version = fields.Integer(required=True, readonly=True)
    tender_revision = fields.Integer(required=True, readonly=True, default=1)
    base_total_minor = fields.Integer(required=True, readonly=True)
    payable_minor = fields.Integer(required=True, readonly=True)
    tip_product_id = fields.Many2one('product.product', required=True, readonly=True, ondelete='restrict')
    canonical = fields.Json(required=True, readonly=True)
    native_contents = fields.Json(required=True, readonly=True)
    fingerprint = fields.Char(required=True, readonly=True)
    projected_snapshot = fields.Json(required=True, readonly=True)
    projected_contents = fields.Json(readonly=True)
    projection_revision = fields.Integer(readonly=True, default=0)
    tenders = fields.Json(readonly=True)
    operation_ids = fields.One2many('pos.revolut.payment.operation', 'authorization_id', readonly=True)
    state = fields.Selection([('prepared','Prepared'),('review_required','Review cart'),
        ('approval_required','Manager approval'),('revoked','Revoked'),('consumed','Consumed')],
        required=True, readonly=True)
    expires_at = fields.Datetime(required=True, readonly=True)
    approved_by = fields.Many2one('res.users', readonly=True, ondelete='restrict')
    approved_at = fields.Datetime(readonly=True)
    rounding = fields.Json(required=True, readonly=True)

    _unique_version = models.Constraint('UNIQUE(company_id, order_uuid, cart_version)', 'Cart versions must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        if not _authority_internal(self.env):
            raise AccessError(_('Cart authority is created only by server preparation.'))
        return super().create(vals_list)

    def write(self, values):
        if not _authority_internal(self.env):
            raise AccessError(_('Cart authority can only change through checked server actions.'))
        immutable = {'pos_order_id','company_id','session_id','config_id','currency_id','order_uuid',
            'cart_version','base_total_minor','tip_product_id','canonical','native_contents','fingerprint','rounding'}
        if immutable.intersection(values):
            raise ValidationError(_('The authorized base cart is immutable.'))
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Retain cart authority for reconciliation.'))

    def _operations(self):
        return self.env['pos.revolut.payment.operation'].sudo().search([('authorization_id','=',self.id)], order='id')

    def _exposed(self):
        return self._operations().filtered(lambda op: not op.retry_safe or op.state == 'verified')

    def _response(self):
        self.ensure_one()
        return {'status': self.state, 'authorization_id': self.id, 'cart_version': self.cart_version,
            'tender_revision': self.tender_revision, 'projection_revision': self.projection_revision,
            'canonical': self.canonical, 'payable_minor': self.payable_minor,
            'remaining_minor': max(0, self.payable_minor - sum(op.amount_minor for op in self._exposed())
                - sum(slot['minor'] for slot in self.tenders or [] if not slot['revolut'])),
            'tenders': self.tenders, 'order_id': self.pos_order_id.id, 'order_uuid': self.order_uuid}

    def _plan(self, tender_plan):
        self.ensure_one()
        if not isinstance(tender_plan, list) or len(tender_plan) > 100:
            raise UserError(_('Provide a bounded tender plan.'))
        slots, seen = [], set()
        normalize = _tender_amount
        for value in tender_plan:
            if not isinstance(value, dict) or set(value) - {'uuid','payment_method_id','amount'}:
                raise UserError(_('The tender plan is invalid.'))
            try:
                uuid = str(UUID(value['uuid']))
            except (KeyError, ValueError, TypeError, AttributeError):
                raise UserError(_('Tender identifiers must be UUIDs.')) from None
            method_id = value.get('payment_method_id')
            if type(method_id) is not int:
                raise UserError(_('Select a configured payment method.'))
            method = self.config_id.payment_method_ids.filtered(lambda item: item.id == method_id)
            if not method or method.company_id != self.company_id or uuid in seen:
                raise UserError(_('The tender method or identifier is invalid.'))
            minor = normalize(self.currency_id, value.get('amount'))[1]
            if minor == 0 or (minor < 0 and not method.is_cash_count):
                raise UserError(_('Only actual cash change may be negative.'))
            seen.add(uuid)
            slots.append({'uuid': uuid, 'method_id': method.id, 'minor': minor,
                'cash': method.is_cash_count, 'revolut': method.use_payment_terminal == 'revolut'})
        slots.sort(key=lambda slot: slot['uuid'])
        by_uuid = {slot['uuid']:slot for slot in slots}
        exposed = self._exposed()
        for op in exposed:
            slot = by_uuid.get(op.payment_line_uuid)
            if not slot or slot['method_id'] != op.payment_method_id.id or slot['minor'] != op.amount_minor:
                raise UserError(_('Keep the original reserved or verified base payment allocation.'))
        # Cash/change is admitted accounting intent and must match the saved
        # draft. Browser done status never verifies another electronic provider.
        persisted = self.pos_order_id.payment_ids.filtered(lambda p: p.payment_method_id.use_payment_terminal != 'revolut')
        for payment in persisted:
            slot = by_uuid.get(payment.uuid)
            if not slot or slot['method_id'] != payment.payment_method_id.id or slot['minor'] != normalize(self.currency_id,payment.amount)[1]:
                raise UserError(_('Synchronize the actual cash and other tenders before preparing.'))
        if any(not slot['revolut'] and slot['uuid'] not in persisted.mapped('uuid') for slot in slots):
            raise UserError(_('Save cash and other tenders before preparation.'))
        cash = sum(slot['minor'] for slot in slots if slot['cash'])
        noncash = sum(slot['minor'] for slot in slots if not slot['cash'])
        if cash < 0:
            raise UserError(_('Cash change cannot exceed cash received.'))
        target = self.base_total_minor
        rounding = self.rounding
        if rounding['enabled']:
            factor = 10 ** self.currency_id.decimal_places
            amount = self.base_total_minor if not rounding['cash_only'] else self.base_total_minor - noncash
            if not rounding['cash_only'] or cash > 0:
                rounded = self.currency_id.round(float_round(amount / factor,
                    precision_rounding=rounding['quantum'], rounding_method=rounding['method']))
                target = normalize(self.currency_id,rounded)[1] + (noncash if rounding['cash_only'] else 0)
            if rounding['cash_only'] and noncash > self.base_total_minor:
                raise UserError(_('Cash rounding cannot authorize extra card payment.'))
        if sum(slot['minor'] for slot in slots) > target:
            raise UserError(_('The tender plan exceeds the authorized remaining order balance.'))
        # Once paid, an enlarged noncash plan cannot reopen rounding capacity.
        old = self.tenders or []
        old_cash = sum(slot['minor'] for slot in old if slot['cash'])
        used = sum(op.amount_minor for op in exposed) + sum(slot['minor'] for slot in old if not slot['revolut'])
        if old and used >= self.payable_minor and target > self.payable_minor and cash >= old_cash:
            raise UserError(_('The authorized order is already fully allocated.'))
        return slots, target

    def _admit(self, method, values):
        self.ensure_one()
        order = self.pos_order_id.with_env(method.env)
        order._revolut_check_prepare_identity(self.order_uuid)
        if self.state != 'prepared' or values.get('cart_version') != self.cart_version or values.get('tender_revision') != self.tender_revision:
            raise UserError(_('Review or prepare the current cart and tender allocation before payment.'))
        if not self._exposed():
            if self.expires_at <= fields.Datetime.now():
                raise UserError(_('Cart authorization expired. Prepare the cart again.'))
            before = self.fingerprint
            priced = order._revolut_price_cart()
            if _digest(order._revolut_authority_contents()) != before or priced['basis'] != self.canonical['basis']:
                raise UserError(_('Pricing or configuration changed. Review the cart before payment.'))
        elif _digest(order._revolut_authority_contents()) != _digest(self.projected_contents or self.native_contents):
            raise UserError(_('The authorized cart changed. Reconcile its existing payment.'))
        if self._exposed():
            # Check the frozen tip policy before another customer can pay.
            order._revolut_terminal_tip_values(1)
        slot = next((slot for slot in self.tenders if slot['uuid'] == values['payment_line_uuid']), None)
        if not slot or slot['method_id'] != method.id or slot['minor'] != values['amount_minor'] or not slot['revolut']:
            raise UserError(_('The payment must match its authorized base allocation.'))
        operations = self._exposed()
        if any(op.payment_line_uuid == values['payment_line_uuid'] for op in operations):
            raise UserError(_('Check the existing payment before another charge.'))
        consumed = sum(op.amount_minor for op in operations)
        other = sum(item['minor'] for item in self.tenders if not item['revolut'])
        if values['amount_minor'] + consumed + other > self.payable_minor:
            raise UserError(_('The payment exceeds the authorized remaining order balance.'))
        return {'authorization_id': self.id, 'cart_version': self.cart_version,
            'tender_revision': self.tender_revision, 'pos_order_id': order.id,
            'financial_snapshot': self.canonical['snapshot']}


class PosOrder(models.Model):
    _inherit = 'pos.order'

    revolut_authorization_id = fields.Many2one('pos.revolut.cart.authorization', readonly=True, copy=False, ondelete='restrict')
    revolut_payable_target = fields.Float(compute='_compute_revolut_target')
    revolut_has_authority_exposure = fields.Boolean(compute='_compute_revolut_target')

    @api.depends_context('uid', 'allowed_company_ids')
    @api.depends('config_id.revolut_user_ids', 'revolut_authorization_id.payable_minor', 'revolut_authorization_id.operation_ids.state',
                 'revolut_authorization_id.operation_ids.terminal_tip_minor', 'lines.refunded_orderline_id', 'lines.qty')
    def _compute_revolut_target(self):
        for order in self:
            try:
                order.config_id._check_revolut_register_access(session=order.session_id, order=order)
                authority = order.revolut_authorization_id.sudo()
                if authority:
                    authority.config_id.with_env(order.env)._check_revolut_register_access(
                        session=authority.session_id, order=order,
                    )
                    for operation in authority._operations():
                        operation.with_env(order.env)._check_revolut_register_access()
                exposed = authority._exposed() if authority else False
                order.revolut_has_authority_exposure = bool(exposed)
                order.revolut_payable_target = ((authority.payable_minor + sum(
                    op.terminal_tip_minor for op in authority._operations() if op.state == 'verified'
                )) / 10**order.currency_id.decimal_places) if exposed else 0
                return_target = order._revolut_return_target_minor()
                if return_target is not None:
                    order.revolut_has_authority_exposure = True
                    order.revolut_payable_target = return_target / 10**order.currency_id.decimal_places
            except AccessError:
                # Native order reads continue, while derived financial state
                # honors the original authority/session even after rollover.
                order.revolut_has_authority_exposure = False
                order.revolut_payable_target = 0

    @api.model
    def _load_pos_data_fields(self, config):
        selected = super()._load_pos_data_fields(config)
        # Native [] means read all, rather than no fields. Keep the persisted
        # authority relation server-side; the checked checkout RPC returns IDs.
        selected = selected or list(self._fields)
        return list(dict.fromkeys(name for name in selected + [
            'revolut_payable_target','revolut_has_authority_exposure'
        ] if name != 'revolut_authorization_id'))

    def _revolut_authority_contents(self):
        self.ensure_one()
        check_line_count_size(len(self.lines))
        result = self._revolut_order_values()
        result.update({'id':self.id, 'company_id':self.company_id.id, 'config_id':self.config_id.id,
            'currency_id':self.currency_id.id, 'currency_rate':self.currency_rate,
            'partner_id':self.partner_id.id, 'preset_id':self.preset_id.id if 'preset_id' in self._fields else False,
            'is_tipped':self.is_tipped, 'tip_amount':self.tip_amount})
        result.pop('state',None)
        result.pop('amount_total',None)
        for values,line in zip(result['lines'],self.lines):
            if len(line.custom_attribute_value_ids) > 100 or any(len(value.custom_value or '') > 1024 for value in line.custom_attribute_value_ids):
                raise UserError(_('Reduce custom attribute values before payment.'))
            values.update({'price_extra':line.price_extra,
                'price_type':line.price_type, 'product_uom_id':line.product_uom_id.id,
                'attributes':sorted(line.attribute_value_ids.ids) if 'attribute_value_ids' in line._fields else [],
                'custom_attributes':sorted([(value.custom_product_template_attribute_value_id.id,value.custom_value or '') for value in line.custom_attribute_value_ids]),
                'combo_parent_id':line.combo_parent_id.id, 'combo_item_id':line.combo_item_id.id,
                'extra_tax_data':line.extra_tax_data})
        result['lines'].sort(key=lambda line:line['uuid'])
        return result

    def _revolut_check_prepare_identity(self, uuid):
        self.ensure_one()
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('Only POS staff can authorize checkout.'))
        self.check_access('write')
        self.config_id._check_revolut_register_access(session=self.session_id, order=self)
        if self.uuid != uuid or self.company_id not in self.env.companies or self.state != 'draft' or self.is_refund:
            raise UserError(_('Select the exact original draft sale for Revolut payment.'))
        if self.session_id.state != 'opened' or self.company_id != self.session_id.company_id or self.config_id != self.session_id.config_id or self.currency_id != self.session_id.currency_id:
            raise UserError(_('The original POS session must be open and ownership unchanged.'))
        if self.env['pos.order'].sudo().search_count([('company_id','=',self.company_id.id),('uuid','=',uuid)]) != 1:
            raise UserError(_('The persisted order identity is ambiguous.'))
        if 'set_tip_after_payment' in self.config_id._fields and self.config_id.set_tip_after_payment:
            raise UserError(_('Disable post-payment tip adjustment and use Revolut terminal tips during payment.'))
        if self.currency_id.decimal_places > 6:
            raise UserError(_('The terminal report cannot represent this currency precision.'))
        if 'table_id' in self._fields and self.table_id and self.config_id not in self.table_id.floor_id.pos_config_ids:
            raise UserError(_('The table does not belong to the original POS configuration.'))

    @api.model
    def revolut_prepare_payment(self, order_id, uuid, expected_cart_version, tender_plan):
        if type(order_id) is not int or type(expected_cart_version) is not int:
            raise UserError(_('Select an exact persisted cart version.'))
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor,self.env.uid,dict(self.env.context))
                    order = env['pos.order'].browse(order_id).exists()
                    if not order:
                        raise UserError(_('Save the draft online before preparing Revolut payment.'))
                    order._revolut_check_prepare_identity(uuid)
                    cursor.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [order.session_id.id])
                    env['pos.revolut.payment.operation'].sudo()._lock_order(order.company_id.id,uuid)
                    order.invalidate_recordset()
                    order._revolut_check_prepare_identity(uuid)
                    with _authority_mutation(env):
                        result = order._revolut_prepare_locked(expected_cart_version,tender_plan)
                    cursor.commit()
                    return result
            except (IntegrityError,SerializationFailure):
                if attempt == 2:
                    raise UserError(_('Another cashier changed checkout. Reload the current cart.')) from None

    def _revolut_prepare_locked(self, expected_cart_version, tender_plan):
        self.ensure_one()
        current = self.revolut_authorization_id.sudo()
        operations = self._locked_revolut_operations_for_order(self.company_id.id,self.uuid)
        exposed = operations.filtered(lambda op:not op.retry_safe or op.state == 'verified')
        if any(not op.authorization_id for op in exposed):
            raise UserError(_('This historical Revolut payment needs audited manager reconciliation before a new allocation.'))
        if current and expected_cart_version not in (0,current.cart_version):
            return {**current._response(),'status':'stale'}
        if exposed:
            if not current or current != exposed.authorization_id or current.state in {'revoked','consumed'}:
                raise UserError(_('Recover the original authorized cart before continuing.'))
            if _digest(self._revolut_authority_contents()) != _digest(current.projected_contents or current.native_contents):
                raise UserError(_('The exposed cart changed; reconcile its original payments.'))
            self._revolut_apply_cash_plan(tender_plan)
            slots,target = current._plan(tender_plan)
            if slots != current.tenders or target != current.payable_minor:
                current.write({'tenders':slots,'payable_minor':target,'tender_revision':current.tender_revision+1})
                self._compute_prices()
            return current._response()
        priced = self._revolut_price_cart()
        native = self._revolut_authority_contents()
        fingerprint = _digest(native)
        if current and current.state != 'revoked' and current.fingerprint == fingerprint and current.canonical['basis'] == priced['basis'] and current.expires_at > fields.Datetime.now():
            slots,target = current._plan(tender_plan)
            if slots != current.tenders or target != current.payable_minor:
                current.write({'tenders':slots,'payable_minor':target,'tender_revision':current.tender_revision+1})
            if current.state == 'review_required' and expected_cart_version == current.cart_version:
                current.write({'state':'approval_required' if priced['approval_required'] else 'prepared'})
            return current._response()
        if current and current.state != 'revoked':
            current.write({'state':'revoked'})
        versions = self.env['pos.revolut.cart.authorization'].sudo().search([('company_id','=',self.company_id.id),('order_uuid','=',self.uuid)],limit=1)
        config = self.config_id
        authority = self.env['pos.revolut.cart.authorization'].sudo().create({
            'pos_order_id':self.id, 'company_id':self.company_id.id, 'session_id':self.session_id.id,
            'config_id':config.id, 'currency_id':self.currency_id.id, 'order_uuid':self.uuid,
            'cart_version':versions.cart_version+1 if versions else 1, 'base_total_minor':priced['total_minor'],
            'payable_minor':priced['total_minor'], 'tip_product_id':config.tip_product_id.id,
            'canonical':priced, 'native_contents':native, 'fingerprint':fingerprint,
            'projected_snapshot':priced['snapshot'], 'tenders':[],
            'state':'review_required' if priced['corrections'] else ('approval_required' if priced['approval_required'] else 'prepared'),
            'expires_at':fields.Datetime.now()+timedelta(minutes=5),
            'rounding':{'enabled':config.cash_rounding,'cash_only':config.only_round_cash_method,
                'quantum':config.rounding_method.rounding if config.rounding_method else 0,
                'method':config.rounding_method.rounding_method if config.rounding_method else 'HALF-UP'},
        })
        slots,target = authority._plan(tender_plan)
        authority.write({'tenders':slots,'payable_minor':target})
        self.write({'revolut_authorization_id':authority.id})
        return authority._response()

    def _revolut_apply_cash_plan(self, tender_plan):
        """Save ordinary cash corrections atomically with the replacement ledger.

        The enclosing preparation owns the order lock and transaction. Other
        electronic tenders and verified Revolut evidence remain immutable.
        _plan validates the completed cash/change arithmetic before commit.
        """
        if not isinstance(tender_plan, list) or len(tender_plan) > 100:
            raise UserError(_('Provide a bounded tender plan.'))
        commands, kept = [], set()
        payments = {payment.uuid:payment for payment in self.payment_ids}
        for slot in tender_plan:
            if not isinstance(slot, dict):
                raise UserError(_('The tender plan is invalid.'))
            method = self.config_id.payment_method_ids.filtered(lambda method:method.id == slot.get('payment_method_id'))
            if not method or not method.is_cash_count:
                continue
            try:
                uuid = str(UUID(slot['uuid']))
            except (KeyError, ValueError, TypeError, AttributeError):
                raise UserError(_('Tender identifiers must be UUIDs.')) from None
            if uuid in kept:
                raise UserError(_('Tender identifiers must be unique.'))
            kept.add(uuid)
            amount = _tender_amount(self.currency_id,slot.get('amount'))[0]
            payment = payments.get(uuid)
            if payment and (payment.payment_method_id != method or payment.revolut_operation_id or payment.revolut_refund_operation_id):
                raise UserError(_('Cash corrections cannot replace electronic payment evidence.'))
            values = {'payment_method_id':method.id,'amount':amount}
            commands.append(Command.update(payment.id,values) if payment else Command.create({**values,'uuid':uuid}))
        commands.extend(Command.delete(payment.id) for payment in self.payment_ids
            if payment.payment_method_id.is_cash_count and payment.uuid not in kept)
        if commands:
            self.write({'payment_ids':commands})

    @api.model
    def revolut_approve_cart(self, order_id, uuid, cart_version):
        if not self.env.user.has_group('point_of_sale.group_pos_manager'):
            raise AccessError(_('Approve the exact cart from an authenticated POS manager session.'))
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor,self.env.uid,dict(self.env.context))
                    order = env['pos.order'].browse(order_id).exists()
                    if not order:
                        raise UserError(_('The cart is unavailable.'))
                    order._revolut_check_prepare_identity(uuid)
                    cursor.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [order.session_id.id])
                    env['pos.revolut.payment.operation'].sudo()._lock_order(order.company_id.id,uuid)
                    order.invalidate_recordset()
                    order._revolut_check_prepare_identity(uuid)
                    authority = order.revolut_authorization_id.sudo()
                    if not authority or authority.cart_version != cart_version or authority.state != 'approval_required' or authority.expires_at <= fields.Datetime.now() or authority.fingerprint != _digest(order._revolut_authority_contents()):
                        raise UserError(_('The pending cart approval is stale. Prepare its exact current version again.'))
                    with _authority_mutation(env):
                        authority.write({'state':'prepared','approved_by':env.uid,'approved_at':fields.Datetime.now()})
                    result = authority._response()
                    cursor.commit()
                    return result
            except SerializationFailure:
                if attempt == 2:
                    raise UserError(_('Another cashier changed checkout. Reload its exact approval version.')) from None

    def action_revolut_approve_cart(self):
        self.ensure_one()
        self.revolut_approve_cart(self.id,self.uuid,self.revolut_authorization_id.cart_version)
        return {'type':'ir.actions.client','tag':'reload'}

    @api.model
    def revolut_checkout_state(self, order_id, uuid):
        order = self.browse(order_id).exists()
        if not order or not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_('The checkout is unavailable.'))
        order.check_access('read')
        order.config_id._check_revolut_register_access(session=order.session_id, order=order)
        if order.uuid != uuid or order.company_id not in self.env.companies:
            raise AccessError(_('Recover the exact original checkout.'))
        return {'data':order.read_pos_data([],order.config_id),
            'authority':order.revolut_authorization_id.sudo()._response() if order.revolut_authorization_id else False}

    @api.model_create_multi
    def create(self, vals_list):
        if not _authority_internal(self.env) and any('revolut_authorization_id' in vals for vals in vals_list):
            raise AccessError(_('Cart authority is server-owned.'))
        return super().create(vals_list)

    def write(self, values):
        if 'revolut_authorization_id' in values and not _authority_internal(self.env):
            raise AccessError(_('Cart authority is server-owned.'))
        return super().write(values)

    def _get_rounded_amount(self, amount, force_round=False):
        self.ensure_one()
        authority = self.revolut_authorization_id.sudo()
        if authority and authority._exposed():
            tips = sum(op.terminal_tip_minor for op in authority._operations() if op.state == 'verified')
            return (authority.payable_minor + tips) / (10 ** self.currency_id.decimal_places)
        return super()._get_rounded_amount(amount,force_round=force_round)

    def _compute_prices(self):
        # Native computation assigns several fields separately. Validate the
        # completed projection, not the intermediate native rounded total that
        # would round a terminal tip a second time.
        with _authority_mutation(self.env):
            result = super()._compute_prices()
            for order in self:
                authority = order.revolut_authorization_id.sudo()
                if authority and authority._exposed():
                    tips = sum(op.terminal_tip_minor for op in authority._operations() if op.state == 'verified')
                    order.amount_total = (authority.payable_minor + tips) / 10**order.currency_id.decimal_places
                    order.amount_difference = order.amount_paid - order.amount_total
        return result

    def _check_revolut_authority_mutation(self):
        if _authority_internal(self.env):
            return
        for order in self:
            authority = order.revolut_authorization_id.sudo()
            if not authority:
                continue
            native = order._revolut_authority_contents()
            expected = authority.projected_contents or authority.native_contents
            if _digest(native) != _digest(expected):
                if authority._exposed():
                    raise UserError(_('The authorized base cart and proven tips are frozen. Reconcile before editing.'))
                with _authority_mutation(self.env):
                    authority.write({'state':'revoked'})
            elif authority._exposed():
                # Direct native tender edits cannot create new cash/card capacity.
                plan = {slot['uuid']:slot for slot in authority.tenders}
                for payment in order.payment_ids:
                    slot = plan.get(payment.uuid)
                    if not slot or slot['method_id'] != payment.payment_method_id.id:
                        raise UserError(_('Prepare the tender plan before changing exposed payments.'))
                    op = authority._operations().filtered(lambda item:item.payment_line_uuid == payment.uuid and (not item.retry_safe or item.state == 'verified'))
                    expected_minor = op._revolut_paid_minor() if len(op) == 1 and op.state == 'verified' else slot['minor']
                    if self.env['pos.revolut.payment.operation'].normalize_amount(order.currency_id,payment.amount)[1] != expected_minor:
                        raise UserError(_('The saved tender must match its authorized allocation.'))
                for slot in authority.tenders:
                    if not slot['revolut'] and slot['uuid'] not in order.payment_ids.mapped('uuid'):
                        raise UserError(_('The admitted cash or other tender cannot be removed outside the ledger.'))

    def _link_revolut_settlement(self, operations, refunds):
        result = super()._link_revolut_settlement(operations, refunds)
        authority = self.revolut_authorization_id.sudo()
        if authority and self.state in {'paid','done'}:
            with _authority_mutation(self.env):
                authority.write({'state':'consumed'})
        return result


class RevolutPaymentOperation(models.Model):
    _inherit = 'pos.revolut.payment.operation'

    authorization_id = fields.Many2one('pos.revolut.cart.authorization', readonly=True, ondelete='restrict', index=True)
    cart_version = fields.Integer(readonly=True)
    tender_revision = fields.Integer(readonly=True)

    @api.model
    def operation_snapshot(self, operation):
        result = super().operation_snapshot(operation)
        if operation.authorization_id:
            result.update({'authorization_id':operation.authorization_id.id,
                'base_amount_minor':operation.amount_minor,
                'cart_version':operation.cart_version,'tender_revision':operation.tender_revision,
                'pos_order_id':operation.pos_order_id.id,
                'projection_revision':operation.authorization_id.projection_revision})
        return result

    def write(self, values):
        if {'authorization_id','cart_version','tender_revision'}.intersection(values):
            raise ValidationError(_('Payment authorization references are immutable.'))
        return super().write(values)

    def _revolut_expected_snapshot(self):
        self.ensure_one()
        return self.authorization_id.projected_snapshot if self.authorization_id else self.financial_snapshot

    def _revolut_project_tip(self):
        self.ensure_one()
        authority = self.authorization_id.sudo()
        if not authority:
            return
        order = authority.pos_order_id
        self._lock_order(self.company_id.id,self.order_uuid)
        operations = authority._operations().filtered(lambda op:op.state == 'verified')
        with _authority_mutation(self.env):
            tip_minor = sum(op.terminal_tip_minor for op in operations)
            tip_uuid = str(uuid5(NAMESPACE_URL,f'revolut-tip:{authority.id}'))
            line = order.lines.filtered(lambda line:line.uuid == tip_uuid)
            values = order._revolut_terminal_tip_values(tip_minor)
            if tip_minor:
                if line:
                    line.write(values)
                else:
                    order.write({'lines':[Command.create({**values,'uuid':tip_uuid})]})
            for operation in operations:
                payment = order.payment_ids.filtered(lambda p:p.uuid == operation.payment_line_uuid)
                values = {'amount':operation._revolut_paid_minor()/10**order.currency_id.decimal_places,
                    'payment_status':'done','transaction_id':operation.revolut_payment_id,
                    'payment_ref_no':operation.revolut_order_id,'revolut_order_id':operation.revolut_order_id,
                    'revolut_payment_intent_id':operation.revolut_payment_intent_id,'revolut_operation_id':operation.id}
                if payment:
                    payment.write(values)
                else:
                    order.write({'payment_ids':[Command.create({**values,'uuid':operation.payment_line_uuid,
                        'payment_method_id':operation.payment_method_id.id})]})
                operation.write({'pos_payment_id':order.payment_ids.filtered(lambda p:p.uuid == operation.payment_line_uuid).id})
            tip_line = order.lines.filtered(lambda item:item.uuid == tip_uuid)
            order.write({'is_tipped':bool(tip_minor),'tip_amount':tip_line.price_subtotal if tip_line else 0})
            order._compute_prices()
            snapshot = self._normalize_financial_snapshot(order._revolut_order_values(),native_order=True)
            authority.write({'projected_snapshot':snapshot,'projected_contents':order._revolut_authority_contents(),
                'projection_revision':authority.projection_revision+1})
        order._check_revolut_authority_mutation()
        order._check_revolut_order()


class PosSession(models.Model):
    _inherit = 'pos.session'

    def write(self, values):
        if values.get('state') in {'closing_control','closed'}:
            for session in self.sorted('id'):
                self.env.cr.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [session.id])
                operations = self.env['pos.revolut.payment.operation'].sudo().search([
                    ('pos_session_id','=',session.id)], order='order_uuid,id')
                refunds = self.env['pos.revolut.refund.operation'].sudo().search([
                    ('order_uuid','!=',False), '|',
                    ('pos_session_id','=',session.id),
                    ('pos_order_id.session_id','=',session.id)], order='order_uuid,id')
                # Return allocations share the order locks used by charges.
                # Keep one stable order even when this session has both kinds.
                keys = {(record.company_id.id, record.order_uuid) for record in operations}
                keys.update((record.company_id.id, record.order_uuid) for record in refunds)
                for company_id, order_uuid in sorted(keys):
                    self.env['pos.revolut.payment.operation']._lock_order(company_id, order_uuid)
                operations.invalidate_recordset()
                refunds.invalidate_recordset()
                if any((not op.retry_safe and op.state != 'verified') or (op.state == 'verified' and (not op.pos_payment_id or op.pos_order_id.state == 'draft')) for op in operations):
                    raise UserError(_('Reconcile or settle the original Revolut payments before closing this session.'))
                if any(refund.state != 'failed' and (
                    refund.state != 'verified' or not refund.pos_payment_id
                    or refund.pos_order_id.state not in {'paid', 'done', 'invoiced'}
                ) for refund in refunds):
                    raise UserError(_('Reconcile or settle the original Revolut refunds before closing this session.'))
        return super().write(values)


class PosCustomAttribute(models.Model):
    _inherit = 'product.attribute.custom.value'

    @api.model_create_multi
    def create(self, vals_list):
        from .pos_order import _revolut_mutation
        with _revolut_mutation(self.env) as mutation:
            lines = self.env['pos.order.line'].browse([vals['pos_order_line_id'] for vals in vals_list if vals.get('pos_order_line_id')])
            mutation.watch(lines.order_id)
            records = super().create(vals_list)
            mutation.watch(records.pos_order_line_id.order_id)
            return records

    def write(self, values):
        from .pos_order import _revolut_mutation
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.pos_order_line_id.order_id)
            if values.get('pos_order_line_id'):
                mutation.watch(self.env['pos.order.line'].browse(values['pos_order_line_id']).order_id)
            return super().write(values)

    def unlink(self):
        from .pos_order import _revolut_mutation
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.pos_order_line_id.order_id)
            return super().unlink()
