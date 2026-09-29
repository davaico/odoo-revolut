"""Reject real Merchant HTTP in the disposable Odoo test runtime."""

import os
from urllib.parse import urlsplit


if os.environ.get("ODOO_REVOLUT_BLOCK_MERCHANT_HTTP") == "1":
    import requests.sessions

    _request = requests.sessions.Session.request
    _merchant_hosts = {
        "merchant.revolut.com",
        "sandbox-merchant.revolut.com",
    }

    def _reject_merchant_requests(self, method, url, *args, **kwargs):
        if urlsplit(str(url)).hostname in _merchant_hosts:
            raise AssertionError("Unmocked Revolut Merchant HTTP request")
        return _request(self, method, url, *args, **kwargs)

    requests.sessions.Session.request = _reject_merchant_requests
