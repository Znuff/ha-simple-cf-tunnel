# Changelog

## 0.4.1

- After **Fix it for me**, the panel shows that Home Assistant is restarting
  and waits for it to come back, instead of showing "Can't reach the add-on:
  Failed to fetch". It then reminds you to confirm the new settings.

## 0.4.0

- Permanent access can be limited to the countries you pick. Cloudflare
  blocks visitors from anywhere else before they reach Home Assistant. Leave
  the list empty to allow every country. This needs the Zone → Zone WAF →
  Edit permission on the API token.

## 0.3.3

- Removed the warning about the URL being public from the Temporary access
  section.

## 0.3.2

- The trusted proxy fix no longer confirms the change itself. Confirm it in
  Home Assistant's own "Confirm new HTTP server configuration" dialog after
  the restart. This fixes the "No pending HTTP config to promote" error when
  both tried to confirm.

## 0.3.1

- Installs and updates now download a prebuilt image instead of building the
  add-on on your device, so they finish in seconds.

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
