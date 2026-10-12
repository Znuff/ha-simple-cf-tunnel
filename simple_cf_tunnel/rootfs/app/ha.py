"""Facts about Home Assistant, from the Supervisor and from HA itself."""

import json
import os
import ssl
import urllib.error
import urllib.request

from proc import log


def core_info():
    """Return (port, uses TLS) for Home Assistant, as reported by the Supervisor."""
    request = urllib.request.Request(
        "http://supervisor/core/info",
        headers={"Authorization": f"Bearer {os.environ['SUPERVISOR_TOKEN']}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        info = json.load(response)["data"]
    return int(info["port"]), bool(info["ssl"])


def origin():
    """Return (origin URL, uses TLS) for Home Assistant."""
    port, uses_tls = core_info()
    return f"{'https' if uses_tls else 'http'}://homeassistant:{port}", uses_tls


def proxy_trusted():
    """True/False if HA does/doesn't accept X-Forwarded-For from this add-on; None if unknown."""
    try:
        url, uses_tls = origin()
        request = urllib.request.Request(url + "/", headers={"X-Forwarded-For": "203.0.113.1"})
        context = ssl._create_unverified_context() if uses_tls else None
        with urllib.request.urlopen(request, timeout=10, context=context):
            return True
    except urllib.error.HTTPError as error:
        return error.code != 400
    except Exception as error:  # noqa: BLE001 - any failure just means "could not check"
        log(f"Trusted proxy check failed: {error}")
        return None
