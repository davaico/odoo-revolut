ARG ODOO_BASE_IMAGE=odoo:18.0-20261015@sha256:1b346c6f9145c79b802b711a554a141acbd0503ed6cd7d31cb3c938889c4cc36
FROM ${ODOO_BASE_IMAGE}

USER root

ARG CHROME_VERSION=153.0.8010.52-1
ARG CHROME_SHA256=29e0e4b5af01213915ffdb7f4e49a11956dc5fc591165c85af8688dcdff907ac

RUN curl --fail --location --show-error \
        --output /tmp/google-chrome-stable.deb \
        "https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION}_amd64.deb" \
    && echo "${CHROME_SHA256}  /tmp/google-chrome-stable.deb" | sha256sum --check --strict \
    && apt-get update \
    && apt-get install --yes --no-install-recommends /tmp/google-chrome-stable.deb python3-websocket \
    && rm -f /tmp/google-chrome-stable.deb \
    && rm -rf /var/lib/apt/lists/*

COPY docker/sitecustomize.py /opt/odoo-test-guard/sitecustomize.py
COPY docker/verify_merchant_http_guard.py /opt/odoo-test-guard/verify_merchant_http_guard.py
ENV PYTHONPATH=/opt/odoo-test-guard

USER odoo
