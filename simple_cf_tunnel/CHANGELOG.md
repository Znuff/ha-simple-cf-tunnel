# Changelog

## 0.3.0

- One-click fix for the trusted proxy warning. It changes Home Assistant's
  HTTP settings using your own login, so the add-on needs no extra
  permissions. Home Assistant restarts, and the change is confirmed when you
  reopen the panel; otherwise Home Assistant reverts it after 5 minutes.

## 0.2.0

- Permanent access on your own hostname: paste a scoped Cloudflare API token,
  pick a domain and subdomain, and the add-on creates the tunnel and DNS
  record.
- Change or repair by running setup again; Remove deletes the tunnel and only
  the DNS records the add-on created.
- The API token is not kept unless you tick "Remember the API token".

## 0.1.0

- First release: temporary access on a random `trycloudflare.com` URL, with
  an expiry of 1 hour, 4 hours, 24 hours or until stopped.
- Warning with instructions when Home Assistant doesn't trust the add-on as a
  reverse proxy.
