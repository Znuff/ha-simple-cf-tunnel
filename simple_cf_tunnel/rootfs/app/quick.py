"""Temporary access: one Cloudflare Quick Tunnel at a time, with an optional expiry."""

import collections
import json
import subprocess
import threading
import time
import urllib.request

import ha
from proc import log, pump, terminate

METRICS_ADDR = "127.0.0.1:36501"
START_TIMEOUT = 60
DURATIONS = {3600, 14400, 86400, None}  # seconds; None = until stopped


def quicktunnel_hostname():
    try:
        with urllib.request.urlopen(f"http://{METRICS_ADDR}/quicktunnel", timeout=2) as response:
            return json.load(response).get("hostname") or None
    except Exception:  # noqa: BLE001 - metrics server not up yet
        return None


class QuickTunnel:
    """idle -> starting -> running -> ended."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.state = "idle"
        self.url = None
        self.expires_at = None
        self.reason = None
        self.output = collections.deque(maxlen=20)

    def status(self):
        with self.lock:
            return {"state": self.state, "url": self.url, "expires_at": self.expires_at, "reason": self.reason}

    def start(self, duration):
        if duration not in DURATIONS:
            raise ValueError("Invalid duration")
        origin, uses_tls = ha.origin()
        args = ["cloudflared", "tunnel", "--no-autoupdate", "--metrics", METRICS_ADDR, "--url", origin]
        if uses_tls:
            args.append("--no-tls-verify")
        with self.lock:
            if self.state in ("starting", "running"):
                raise RuntimeError("A temporary tunnel is already running")
            self.output.clear()
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.proc, self.state, self.url, self.expires_at, self.reason = proc, "starting", None, None, None
        log(f"Starting Quick Tunnel to {origin}")
        threading.Thread(target=pump, args=(proc, "quick", self.output), daemon=True).start()
        threading.Thread(target=self._watch, args=(proc, duration), daemon=True).start()

    def stop(self, reason="Stopped"):
        with self.lock:
            proc = self.proc
            if proc is None:
                return
            self.proc, self.state, self.url, self.expires_at, self.reason = None, "ended", None, None, reason
        log(f"Quick Tunnel: {reason}")
        terminate(proc)

    def _watch(self, proc, duration):
        deadline = time.time() + START_TIMEOUT
        while (hostname := quicktunnel_hostname()) is None:
            if proc.poll() is not None:
                return self._ended(proc, f"cloudflared exited with code {proc.returncode} before the tunnel came up")
            if time.time() > deadline:
                terminate(proc)
                return self._ended(proc, "Timed out waiting for Cloudflare to assign a URL")
            time.sleep(1)

        with self.lock:
            if self.proc is not proc:
                return
            self.state, self.url = "running", f"https://{hostname}"
            self.expires_at = time.time() + duration if duration else None
            expires_at = self.expires_at
        log(f"Quick Tunnel is up at https://{hostname}")

        while proc.poll() is None:
            if expires_at and time.time() >= expires_at:
                terminate(proc)
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
        log(f"Quick Tunnel: {self.reason}")
