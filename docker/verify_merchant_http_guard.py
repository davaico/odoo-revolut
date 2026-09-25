"""Prove the test image rejects both Merchant API hosts before Odoo starts."""

import requests


for host in ("sandbox-merchant.revolut.com", "merchant.revolut.com"):
    try:
        requests.get(f"https://{host}/api/terminals", timeout=1)
    except AssertionError as error:
        if str(error) != "Unmocked Revolut Merchant HTTP request":
            raise
    else:
        raise AssertionError(f"Merchant HTTP guard did not reject {host}")
