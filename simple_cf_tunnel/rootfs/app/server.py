"""Simple Cloudflare Tunnel: Ingress UI and JSON API for the permanent and temporary tunnels."""

import json
import pathlib
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ha
from cloudflare import CloudflareError
from permanent import Permanent, SetupConflict
from proc import log
from quick import QuickTunnel

INGRESS_PORT = 8099
INGRESS_PROXY = "172.30.32.2"  # Supervisor's Ingress proxy; nothing else may reach the UI
CSRF_HEADER = "simple-cf-tunnel"
PAGE = pathlib.Path(__file__).with_name("index.html")

QUICK = None
PERMANENT = None
PROXY = {"trusted": None, "ha_port": None}


def recheck_proxy():
    PROXY["trusted"] = ha.proxy_trusted()
    try:
        # The panel's "fix it" flow must keep HA on the port it runs on now.
        PROXY["ha_port"] = ha.core_info()[0]
    except Exception as error:  # noqa: BLE001 - the panel then offers only manual steps
        log(f"Could not read Home Assistant's port: {error}")


def full_status():
    return {
        "permanent": PERMANENT.status(),
        "quick": QUICK.status(),
        "proxy_trusted": PROXY["trusted"],
        "ha_port": PROXY["ha_port"],
        "now": time.time(),
    }


def post_action(path, body):
    """Run one POST action; returns an extra payload to merge into the response, or None."""
    if path == "/api/quick/start":
        threading.Thread(target=recheck_proxy, daemon=True).start()
        QUICK.start(body.get("duration"))
    elif path == "/api/quick/stop":
        QUICK.stop()
    elif path == "/api/recheck":
        recheck_proxy()
    elif path == "/api/permanent/zones":
        return {"zones": PERMANENT.zones(body.get("token"))}
    elif path == "/api/permanent/setup":
        threading.Thread(target=recheck_proxy, daemon=True).start()
        PERMANENT.setup(body.get("token"), body.get("zone_id"), body.get("subdomain"),
                        bool(body.get("remember")), bool(body.get("replace")))
    elif path == "/api/permanent/remove":
        PERMANENT.remove(body.get("token"))
    elif path == "/api/permanent/forget-token":
        PERMANENT.forget_token()
    else:
        raise LookupError
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "SimpleCfTunnel"

    def log_message(self, *args):
        pass

    def do_GET(self):
        if not self._from_ingress():
            return
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            base = json.dumps(self.headers.get("X-Ingress-Path", "")).replace("</", "<\\/")
            body = PAGE.read_text(encoding="utf-8").replace("__INGRESS_PATH__", base).encode()
            self._send(200, body, "text/html; charset=utf-8")
        elif path == "/api/state":
            self._json(200, full_status())
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._from_ingress():
            return
        # A custom header forces a CORS preflight, so other origins can't forge these requests.
        if self.headers.get("X-Requested-With") != CSRF_HEADER:
            return self._json(403, {"error": "Missing request header"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._json(400, {"error": "Invalid JSON"})

        try:
            extra = post_action(self.path.split("?", 1)[0], body)
        except LookupError:
            return self._json(404, {"error": "Not found"})
        except SetupConflict as conflict:
            return self._json(409, {"error": str(conflict), "conflict": conflict.records})
        except (ValueError, RuntimeError) as error:
            return self._json(400, {"error": str(error)})
        except CloudflareError as error:
            log(f"Cloudflare API error: {error}")
            return self._json(502, {"error": str(error)})
        except Exception as error:  # noqa: BLE001 - surface Supervisor/cloudflared failures in the UI
            log(f"Action failed: {error!r}")
            return self._json(500, {"error": f"Something went wrong: {error}"})
        self._json(200, {**full_status(), **(extra or {})})

    def _from_ingress(self):
        if self.client_address[0] == INGRESS_PROXY:
            return True
        self._json(403, {"error": "Forbidden"})
        return False

    def _json(self, status, payload):
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    global QUICK, PERMANENT
    # A previous controller that crashed may have left its cloudflared processes behind.
    subprocess.run(["pkill", "-x", "cloudflared"], check=False)
    QUICK, PERMANENT = QuickTunnel(), Permanent()
    threading.Thread(target=recheck_proxy, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", INGRESS_PORT), Handler)

    def shutdown(*_):
        QUICK.stop("Add-on stopped")
        PERMANENT.runner.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    log(f"Listening on port {INGRESS_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
