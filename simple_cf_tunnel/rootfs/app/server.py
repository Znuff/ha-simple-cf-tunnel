"""Simple Cloudflare Tunnel: Ingress UI and Quick Tunnel manager."""

import collections
import json
import os
import pathlib
import signal
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INGRESS_PORT = 8099
INGRESS_PROXY = "172.30.32.2"  # Supervisor's Ingress proxy; nothing else may reach the UI
METRICS_ADDR = "127.0.0.1:36501"
START_TIMEOUT = 60
DURATIONS = {3600, 14400, 86400, None}  # seconds; None = until stopped
CSRF_HEADER = "simple-cf-tunnel"
PAGE = pathlib.Path(__file__).with_name("index.html")


def log(message):
    print(f"[controller] {message}", flush=True)


def ha_origin():
    """Return (origin URL, uses TLS) for Home Assistant, as reported by the Supervisor."""
    request = urllib.request.Request(
        "http://supervisor/core/info",
        headers={"Authorization": f"Bearer {os.environ['SUPERVISOR_TOKEN']}"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        info = json.load(response)["data"]
    scheme = "https" if info["ssl"] else "http"
    return f"{scheme}://homeassistant:{info['port']}", bool(info["ssl"])


def check_proxy_trusted():
    """True/False if HA does/doesn't accept X-Forwarded-For from this add-on; None if unknown."""
    try:
        origin, uses_tls = ha_origin()
        request = urllib.request.Request(origin + "/", headers={"X-Forwarded-For": "203.0.113.1"})
        context = ssl._create_unverified_context() if uses_tls else None
        with urllib.request.urlopen(request, timeout=10, context=context):
            return True
    except urllib.error.HTTPError as error:
        return error.code != 400
    except Exception as error:  # noqa: BLE001 - any failure just means "could not check"
        log(f"Trusted proxy check failed: {error}")
        return None


def quicktunnel_hostname():
    try:
        with urllib.request.urlopen(f"http://{METRICS_ADDR}/quicktunnel", timeout=2) as response:
            return json.load(response).get("hostname") or None
    except Exception:  # noqa: BLE001 - metrics server not up yet
        return None


class Tunnel:
    """One Quick Tunnel at a time: idle -> starting -> running -> ended."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.state = "idle"
        self.url = None
        self.expires_at = None
        self.reason = None
        self.output = collections.deque(maxlen=20)

    def snapshot(self):
        with self.lock:
            return {
                "state": self.state,
                "url": self.url,
                "expires_at": self.expires_at,
                "reason": self.reason,
            }

    def start(self, duration):
        origin, uses_tls = ha_origin()
        args = ["cloudflared", "tunnel", "--no-autoupdate", "--metrics", METRICS_ADDR, "--url", origin]
        if uses_tls:
            args.append("--no-tls-verify")
        with self.lock:
            if self.state in ("starting", "running"):
                raise RuntimeError("A tunnel is already running")
            self.output.clear()
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.proc, self.state, self.url, self.expires_at, self.reason = proc, "starting", None, None, None
        log(f"Starting Quick Tunnel to {origin}")
        threading.Thread(target=self._pump, args=(proc,), daemon=True).start()
        threading.Thread(target=self._watch, args=(proc, duration), daemon=True).start()

    def stop(self, reason="Stopped"):
        with self.lock:
            proc = self.proc
            if proc is None:
                return
            self.proc, self.state, self.url, self.expires_at, self.reason = None, "ended", None, None, reason
        log(reason)
        _terminate(proc)

    def _pump(self, proc):
        for line in proc.stdout:
            line = line.rstrip()
            print(f"[cloudflared] {line}", flush=True)
            self.output.append(line)

    def _watch(self, proc, duration):
        deadline = time.time() + START_TIMEOUT
        while (hostname := quicktunnel_hostname()) is None:
            if proc.poll() is not None:
                return self._ended(proc, f"cloudflared exited with code {proc.returncode} before the tunnel came up")
            if time.time() > deadline:
                _terminate(proc)
                return self._ended(proc, "Timed out waiting for Cloudflare to assign a URL")
            time.sleep(1)

        with self.lock:
            if self.proc is not proc:
                return
            self.state, self.url = "running", f"https://{hostname}"
            self.expires_at = time.time() + duration if duration else None
            expires_at = self.expires_at
        log(f"Tunnel is up at https://{hostname}")

        while proc.poll() is None:
            if expires_at and time.time() >= expires_at:
                _terminate(proc)
                return self._ended(proc, "Expired")
            time.sleep(1)
        self._ended(proc, f"cloudflared exited unexpectedly with code {proc.returncode}")

    def _ended(self, proc, reason):
        with self.lock:
            if self.proc is not proc:
                return
            last = self.output[-1] if self.output and reason != "Expired" else None
            self.proc, self.state, self.url, self.expires_at = None, "ended", None, None
            self.reason = f"{reason}: {last}" if last else reason
        log(self.reason)


def _terminate(proc):
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


TUNNEL = Tunnel()
PROXY = {"trusted": None}


def recheck_proxy():
    PROXY["trusted"] = check_proxy_trusted()


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
            self._json(200, {**TUNNEL.snapshot(), "proxy_trusted": PROXY["trusted"], "now": time.time()})
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

        path = self.path.split("?", 1)[0]
        if path == "/api/start":
            duration = body.get("duration")
            if duration not in DURATIONS:
                return self._json(400, {"error": "Invalid duration"})
            threading.Thread(target=recheck_proxy, daemon=True).start()
            try:
                TUNNEL.start(duration)
            except RuntimeError as error:
                return self._json(409, {"error": str(error)})
            except Exception as error:  # noqa: BLE001 - surface Supervisor/cloudflared failures in the UI
                log(f"Start failed: {error}")
                return self._json(500, {"error": f"Could not start the tunnel: {error}"})
        elif path == "/api/stop":
            TUNNEL.stop()
        elif path == "/api/recheck":
            recheck_proxy()
        else:
            return self._json(404, {"error": "Not found"})
        self._json(200, {**TUNNEL.snapshot(), "proxy_trusted": PROXY["trusted"], "now": time.time()})

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
    # A previous controller that crashed may have left its cloudflared behind.
    subprocess.run(["pkill", "-x", "cloudflared"], check=False)
    threading.Thread(target=recheck_proxy, daemon=True).start()

    server = ThreadingHTTPServer(("0.0.0.0", INGRESS_PORT), Handler)

    def shutdown(*_):
        TUNNEL.stop("Add-on stopped")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    log(f"Listening on port {INGRESS_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
