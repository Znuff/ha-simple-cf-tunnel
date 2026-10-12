"""Permanent access: a remote-managed Cloudflare Tunnel on one hostname, provisioned through the API."""

import collections
import json
import os
import pathlib
import re
import secrets
import subprocess
import threading
import time
import urllib.parse
import urllib.request

import ha
from cloudflare import Cloudflare, CloudflareError
from proc import log, pump, terminate

STATE_FILE = pathlib.Path("/data/state.json")
METRICS_ADDR = "127.0.0.1:36500"
SUBDOMAIN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")

# Pre-fills Cloudflare's "Create API token" form. The UI also lists these in words,
# in case the dashboard doesn't recognise a key.
TOKEN_URL = "https://dash.cloudflare.com/profile/api-tokens?" + urllib.parse.urlencode({
    "permissionGroupKeys": json.dumps([
        {"key": "argotunnel", "type": "edit"},
        {"key": "zone", "type": "read"},
        {"key": "dns", "type": "edit"},
    ], separators=(",", ":")),
    "accountId": "*",
    "zoneId": "all",
    "name": "Home Assistant tunnel",
})


class SetupConflict(Exception):
    """The hostname already has DNS records this add-on didn't create."""

    def __init__(self, hostname, records):
        super().__init__(f"{hostname} already has DNS records")
        self.records = records


def command():
    # The run token comes from the TUNNEL_TOKEN environment variable, keeping it out of `ps`.
    return ["cloudflared", "tunnel", "--no-autoupdate", "--metrics", METRICS_ADDR, "run"]


class Runner:
    """Keeps cloudflared running with the tunnel's run token, restarting it with backoff."""

    def __init__(self):
        self.lock = threading.Lock()
        self.generation = 0
        self.proc = None
        self.last_exit = None
        self.output = collections.deque(maxlen=20)

    def start(self, run_token):
        self.stop()
        with self.lock:
            self.generation += 1
            generation, self.last_exit = self.generation, None
        threading.Thread(target=self._loop, args=(generation, run_token), daemon=True).start()

    def stop(self):
        with self.lock:
            self.generation += 1
            proc, self.proc = self.proc, None
        if proc:
            terminate(proc)

    def connected(self):
        try:
            with urllib.request.urlopen(f"http://{METRICS_ADDR}/ready", timeout=2) as response:
                return response.status == 200
        except Exception:  # noqa: BLE001 - not running, or no edge connection yet
            return False

    def _loop(self, generation, run_token):
        delay = 5
        while True:
            with self.lock:
                if generation != self.generation:
                    return
                proc = subprocess.Popen(
                    command(), env={**os.environ, "TUNNEL_TOKEN": run_token},
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
                self.proc = proc
            started = time.time()
            pump(proc, "tunnel", self.output)
            proc.wait()
            with self.lock:
                if generation != self.generation:
                    return
                self.proc = None
                last = self.output[-1] if self.output else ""
                self.last_exit = f"cloudflared exited with code {proc.returncode}: {last}".rstrip(": ")
            log(f"{self.last_exit}; restarting in {delay}s")
            time.sleep(delay)
            delay = 5 if time.time() - started > 60 else min(delay * 2, 60)


class Permanent:
    def __init__(self):
        self.lock = threading.Lock()  # one setup/remove at a time
        self.runner = Runner()
        self.state = self._load()
        self.current_origin = None
        if self.state.get("tunnel_token"):
            self.runner.start(self.state["tunnel_token"])
        threading.Thread(target=self._refresh_origin, daemon=True).start()

    # ---- status -------------------------------------------------------------

    def status(self):
        state = self.state
        configured = bool(state.get("tunnel_token"))
        return {
            "configured": configured,
            "hostname": state.get("hostname"),
            "connected": configured and self.runner.connected(),
            "last_exit": self.runner.last_exit,
            "token_saved": bool(state.get("api_token")),
            "origin_changed": bool(
                configured and self.current_origin and self.current_origin != state.get("origin")
            ),
            "token_url": TOKEN_URL,
        }

    def _refresh_origin(self):
        try:
            self.current_origin = ha.origin()[0]
        except Exception as error:  # noqa: BLE001 - only used for a warning
            log(f"Could not read Home Assistant's port: {error}")

    # ---- API-backed actions ---------------------------------------------------

    def api(self, supplied_token):
        token = (supplied_token or "").strip() or self.state.get("api_token")
        if not token:
            raise ValueError("Paste your Cloudflare API token first")
        return Cloudflare(token)

    def zones(self, supplied_token):
        cf = self.api(supplied_token)
        zones = cf.call("GET", "/zones", params={"status": "active", "per_page": 50})
        return [{"id": z["id"], "name": z["name"]} for z in zones]

    def setup(self, supplied_token, zone_id, subdomain, remember, replace):
        subdomain = (subdomain or "").strip().lower()
        if not SUBDOMAIN.match(subdomain):
            raise ValueError("Enter a subdomain such as ha or home.lab")
        with self.lock:
            cf = self.api(supplied_token)
            zone = cf.call("GET", f"/zones/{zone_id}")
            account_id, hostname = zone["account"]["id"], f"{subdomain}.{zone['name']}"
            origin, uses_tls = ha.origin()
            state, tag = self.state, self._tag()

            tunnel_id = self._ensure_tunnel(cf, account_id)
            state.update(account_id=account_id, tunnel_id=tunnel_id)
            self._save()  # a retry after a failure below reuses this tunnel

            run_token = cf.call("GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token")
            rule = {"hostname": hostname, "service": origin}
            if uses_tls:
                rule["originRequest"] = {"noTLSVerify": True}  # HA's certificate won't match "homeassistant"
            cf.call("PUT", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
                    {"config": {"ingress": [rule, {"service": "http_status:404"}]}})

            record_id = self._ensure_dns(cf, zone_id, hostname, f"{tunnel_id}.cfargotunnel.com", tag, replace)
            old_zone, old_record = state.get("zone_id"), state.get("dns_record_id")
            if old_record and (old_zone, old_record) != (zone_id, record_id):
                self._delete_own_record(cf, old_zone, old_record)  # hostname changed: new record exists first

            state.update(zone_id=zone_id, hostname=hostname, dns_record_id=record_id,
                         tunnel_token=run_token, origin=origin)
            if remember:
                state["api_token"] = cf.token
            else:
                state.pop("api_token", None)
            self._save()
            self.current_origin = origin
            self.runner.start(run_token)
        log(f"Permanent tunnel set up for https://{hostname}")

    def remove(self, supplied_token):
        with self.lock:
            cf = self.api(supplied_token)
            state = self.state
            if state.get("dns_record_id"):
                self._delete_own_record(cf, state["zone_id"], state["dns_record_id"])
            self.runner.stop()
            if state.get("tunnel_id"):
                base = f"/accounts/{state['account_id']}/cfd_tunnel/{state['tunnel_id']}"
                _ignore_missing(cf.call, "DELETE", base + "/connections")
                _ignore_missing(cf.call, "DELETE", base)
            self.state = {"install_id": state["install_id"]}
            self._save()
        log("Permanent tunnel removed")

    def forget_token(self):
        with self.lock:
            self.state.pop("api_token", None)
            self._save()

    # ---- helpers ---------------------------------------------------------------

    def _tag(self):
        return f"managed-by: simple-cf-tunnel/{self.state['install_id']}"

    def _ensure_tunnel(self, cf, account_id):
        state = self.state
        if state.get("tunnel_id") and state.get("account_id") == account_id:
            try:
                tunnel = cf.call("GET", f"/accounts/{account_id}/cfd_tunnel/{state['tunnel_id']}")
                if not tunnel.get("deleted_at"):
                    return tunnel["id"]
            except CloudflareError as error:
                if error.status != 404:
                    raise
        name = f"ha-{state['install_id']}"
        existing = cf.call("GET", f"/accounts/{account_id}/cfd_tunnel", params={"name": name, "is_deleted": "false"})
        if existing:
            return existing[0]["id"]
        return cf.call("POST", f"/accounts/{account_id}/cfd_tunnel", {"name": name, "config_src": "cloudflare"})["id"]

    def _ensure_dns(self, cf, zone_id, hostname, target, tag, replace):
        records = cf.call("GET", f"/zones/{zone_id}/dns_records", params={"name.exact": hostname})
        ours = [r for r in records if r.get("comment") == tag]
        others = [r for r in records if r.get("comment") != tag]
        if others and not replace:
            raise SetupConflict(hostname, [{"type": r["type"], "content": r["content"]} for r in others])
        for record in others + ours[1:]:
            cf.call("DELETE", f"/zones/{zone_id}/dns_records/{record['id']}")
        body = {"type": "CNAME", "name": hostname, "content": target, "proxied": True, "ttl": 1, "comment": tag}
        if ours:
            return cf.call("PUT", f"/zones/{zone_id}/dns_records/{ours[0]['id']}", body)["id"]
        return cf.call("POST", f"/zones/{zone_id}/dns_records", body)["id"]

    def _delete_own_record(self, cf, zone_id, record_id):
        """Delete a DNS record only if it still carries this install's tag."""
        try:
            record = cf.call("GET", f"/zones/{zone_id}/dns_records/{record_id}")
        except CloudflareError as error:
            if error.status == 404:
                return
            raise
        if record.get("comment") == self._tag():
            cf.call("DELETE", f"/zones/{zone_id}/dns_records/{record_id}")

    def _load(self):
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            state = {}
        state.setdefault("install_id", secrets.token_hex(3))
        return state

    def _save(self):
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATE_FILE)


def _ignore_missing(fn, *args):
    try:
        fn(*args)
    except CloudflareError as error:
        if error.status != 404:
            raise
