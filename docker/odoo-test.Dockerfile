FROM odoo:19.0@sha256:144175ec0039d52daff1d79f7e51c9281ca3c98b96c830feb49d09764a9f5d7c

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
