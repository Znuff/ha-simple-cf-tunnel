# Simple Cloudflare Tunnel

Give someone temporary access to your Home Assistant through a Cloudflare
[Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
No Cloudflare account, domain or port forwarding needed.

## How to use it

1. Start the add-on and open **Cloudflare Tunnel** in the sidebar.
2. Pick how long the tunnel stays open: 1 hour, 4 hours (default), 24 hours,
   or until you stop it.
3. Click **Start tunnel**. After a few seconds you get a random
   `https://….trycloudflare.com` URL.
4. Share the URL. Click **Stop tunnel** when you're done, or let it expire.

The URL stops working for good when the tunnel stops. Every new tunnel gets a
new URL. Restarting the add-on or the host also ends the tunnel.

## Security

Anyone who has the URL can reach your Home Assistant login page. Your Home
Assistant login is the only thing protecting it.

- Create a separate, non-admin user for the person you share with
  (Settings → People), and remove it afterwards.
- Keep the tunnel open only as long as needed.

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

## Limits

These come from Cloudflare Quick Tunnels:

- Meant for testing and short-term sharing, with no uptime guarantee.
- At most 200 requests in flight at once; more get HTTP 429.
- Server-Sent Events are not supported.
