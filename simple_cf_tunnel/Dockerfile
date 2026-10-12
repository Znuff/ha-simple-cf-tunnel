FROM ghcr.io/hassio-addons/base:21.0.8

ARG BUILD_ARCH="amd64"
ARG CLOUDFLARED_VERSION="2026.10.0"

RUN set -eux; \
    apk add --no-cache python3; \
    case "${BUILD_ARCH}" in \
        aarch64) cf_arch="arm64" ;; \
        *) cf_arch="${BUILD_ARCH}" ;; \
    esac; \
    wget -q -O /usr/bin/cloudflared \
        "https://github.com/cloudflare/cloudflared/releases/download/${CLOUDFLARED_VERSION}/cloudflared-linux-${cf_arch}"; \
    chmod +x /usr/bin/cloudflared

COPY rootfs /

RUN chmod +x /etc/s6-overlay/s6-rc.d/controller/run

ARG BUILD_VERSION
LABEL \
    io.hass.name="Simple Cloudflare Tunnel" \
    io.hass.type="addon" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.source="https://github.com/Znuff/ha-simple-cf-tunnel" \
    org.opencontainers.image.licenses="MIT"
