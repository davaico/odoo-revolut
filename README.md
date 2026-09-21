# Odoo–Revolut Terminal Integration

This repository will contain an Odoo 19 Point of Sale addon connecting Odoo POS to a Revolut payment terminal through the Revolut Merchant API.

The target flow sends the POS payment amount to the terminal, tracks the payment to a final state, and confirms the Odoo order only after verified success. It will handle declined, failed, cancelled, and timed-out payments; support full and partial refunds; and retain Revolut transaction references for reconciliation.

Revolut credentials and API operations must remain on the Odoo server. No API secret may be sent to or stored in the POS browser.

Implementation has not started. See [AGENTS.md](AGENTS.md) for repository boundaries and development requirements.
