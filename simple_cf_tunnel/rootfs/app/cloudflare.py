"""Minimal Cloudflare v4 API client."""

import json
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.cloudflare.com/client/v4"


class CloudflareError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class Cloudflare:
    def __init__(self, token):
        self.token = token

    def call(self, method, path, body=None, params=None):
        url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
        request = urllib.request.Request(
            url,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status, payload = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            status = error.code
            try:
                payload = json.load(error)
            except ValueError:
                payload = {}
        if not payload.get("success"):
            details = "; ".join(e.get("message", "") for e in payload.get("errors") or []) or f"HTTP {status}"
            if status in (401, 403):
                details = f"Cloudflare rejected the API token, or it lacks a permission ({details})"
            raise CloudflareError(status, details)
        return payload.get("result")
