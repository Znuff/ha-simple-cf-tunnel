# Simple Cloudflare Tunnel

Reach Home Assistant from anywhere through Cloudflare, without opening ports.
Open **Cloudflare Tunnel** in the sidebar; everything is set up there.

- **Permanent access:** your own hostname, such as `ha.example.com`, on a
  domain you have in Cloudflare.
- **Temporary access:** a random `trycloudflare.com` URL for sharing, no
  Cloudflare account needed.

Both can run at the same time.

## Permanent access

### What you need

- A Cloudflare account with your domain on it (Cloudflare handles its DNS).
- A Cloudflare API token with these permissions:
  - Account → Cloudflare Tunnel → Edit
  - Zone → Zone → Read
  - Zone → DNS → Edit

  The panel has a link that pre-fills the token form. You can limit the
  token's Zone Resources to the one domain you'll use.

  To limit access by country, also add Zone → Zone WAF → Edit.

### Set up

1. Create the token and paste it into the panel, then click
   **Load my domains**.
2. Pick the domain and type a subdomain (default `ha`).
3. Optionally, pick the countries allowed to reach it (see below).
4. Click **Set up**.

The add-on creates a tunnel named `ha-<id>`, points it at Home Assistant, and
creates a proxied DNS record for your hostname. Your Home Assistant port and
TLS setting are detected automatically.

If the hostname already has DNS records, the add-on shows them and only
replaces them after you confirm.

### Limit access by country

Under **Allow access only from these countries**, type a country name or
code and press Enter, or pick it from the suggestions. Leave the list empty to
allow every country.

With countries picked, the add-on creates a Cloudflare WAF custom rule on your
domain that blocks requests to your hostname from anywhere else. Cloudflare
blocks them at its edge, before they reach the tunnel. The rule's description
is the same `managed-by: simple-cf-tunnel/<id>` tag as the DNS record, and the
add-on leaves your own custom rules alone. Cloudflare's free plan allows 5
custom rules per domain; this uses one.

This is a simple filter, not a replacement for a strong password: a visitor
using a VPN in an allowed country gets through. It also blocks you, and the
companion app, when you travel to a country that isn't on the list, so add
those countries before you go.

The country is Cloudflare's guess from the visitor's IP address. It only
applies to permanent access: temporary `trycloudflare.com` URLs can't be
limited.

To change the list, use **Change or repair** and run setup again. This needs
the Zone WAF permission on the token. If you saved a token without it, add the
permission to that token in the Cloudflare dashboard; the token value stays
the same.

### The API token

By default the API token is **not** kept: after setup, only the tunnel's own
run token stays on the device. It can run the tunnel, but cannot change DNS or
anything else in your account. Changing the hostname, repairing or removing
the tunnel asks for the API token again.

Tick "Remember the API token" during setup to keep it instead, and use
**Forget API token** to drop it later. A remembered token is stored in the
add-on's data, which is included in Home Assistant backups.

### Change, repair or remove

- **Change or repair:** run setup again, with a new hostname or the same one.
  This also fixes a tunnel or DNS record deleted in the Cloudflare dashboard,
  and updates the tunnel after you change Home Assistant's port or TLS
  setting (the panel tells you when that happens).
- **Remove:** deletes the tunnel, the DNS record and the country rule. Press it before
  uninstalling the add-on, otherwise the tunnel stays in your Cloudflare
  account.

The add-on only ever deletes DNS records it created. It recognises them by a
`managed-by: simple-cf-tunnel/<id>` comment on the record.

## Temporary access

1. Pick how long the tunnel stays open: 1 hour, 4 hours (default), 24 hours,
   or until you stop it.
2. Click **Start tunnel**. After a few seconds you get a random
   `https://….trycloudflare.com` URL.
3. Share the URL. Click **Stop tunnel** when you're done, or let it expire.

The URL stops working for good when the tunnel stops. Every new tunnel gets a
new URL. Restarting the add-on or the host also ends it.

Anyone who has the URL can reach your Home Assistant login page. Create a
separate, non-admin user for the person you share with (Settings → People),
and remove it afterwards.

Quick Tunnels are meant for testing and short-term sharing: they have no
uptime guarantee, allow at most 200 requests in flight, and don't support
Server-Sent Events.

## Home Assistant setup: trusted proxy

Home Assistant rejects requests coming through a proxy it doesn't trust, and
visitors see `400: Bad Request`. The add-on checks this and shows a warning in
its panel if it's not set up.

### Automatic fix

The warning has a **Fix it for me** button. It changes the setting using your
own Home Assistant login (the panel runs inside Home Assistant), so the add-on
itself needs no extra permissions. It keeps your other HTTP settings, adds
`172.30.33.0/24` as a trusted proxy, and Home Assistant restarts.

The panel shows a progress bar while Home Assistant restarts and updates on
its own when it's back. After the restart, Home Assistant shows a "Confirm new HTTP server
configuration" dialog. Click **Confirm** to keep the change. If you don't
confirm within 5 minutes, Home Assistant reverts it on its own.

The button only appears when the panel is opened inside Home Assistant on a
version that supports changing HTTP settings this way.

### Manual fix

In **Settings → System → Network → HTTP server**, enable "Trust
X-Forwarded-For" and add `172.30.33.0/24` as a trusted proxy. Or add this to
`configuration.yaml`:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.30.33.0/24
```

Restart Home Assistant afterwards.
