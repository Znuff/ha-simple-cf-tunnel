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

### Set up

1. Create the token and paste it into the panel, then click
   **Load my domains**.
2. Pick the domain and type a subdomain (default `ha`).
3. Click **Set up**.

The add-on creates a tunnel named `ha-<id>`, points it at Home Assistant, and
creates a proxied DNS record for your hostname. Your Home Assistant port and
TLS setting are detected automatically.

If the hostname already has DNS records, the add-on shows them and only
replaces them after you confirm.

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
- **Remove:** deletes the tunnel and the DNS record. Press it before
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
