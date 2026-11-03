-- A whole-database copy retains ORM copy=False fields. Remove live keys and
-- revoke environment-backed authorities too, across every company.
UPDATE pos_revolut_merchant_credential
   SET secret_key = NULL,
       revoked = true
 WHERE environment = 'production';

-- Preserve terminal bindings and historical operation identities. Never turn
-- a live terminal method into a manually confirmable tender.
UPDATE pos_payment_method
   SET active = false
 WHERE use_payment_terminal = 'revolut'
   AND revolut_environment = 'production';

UPDATE ir_cron
   SET active = false
 WHERE id IN (
       SELECT res_id
         FROM ir_model_data
        WHERE module = 'pos_revolut'
          AND model = 'ir.cron'
          AND name IN ('ir_cron_reconcile_payments', 'ir_cron_reconcile_refunds')
);
