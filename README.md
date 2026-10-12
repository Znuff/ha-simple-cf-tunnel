# Simple Cloudflare Tunnel for Home Assistant

A Home Assistant add-on that gives someone temporary access to your Home
Assistant through a Cloudflare Quick Tunnel: a random `trycloudflare.com` URL,
no Cloudflare account, domain or port forwarding needed. Tunnels expire after
a duration you pick.

## Install

[![Add repository to your Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FZnuff%2Fha-simple-cf-tunnel)

Or manually: **Settings → Add-ons → Add-on store → ⋮ → Repositories**, add
`https://github.com/Znuff/ha-simple-cf-tunnel`, then install
**Simple Cloudflare Tunnel**.

The add-on is built on your device during install, so the first install takes
a minute or two.

See [the add-on documentation](simple_cf_tunnel/DOCS.md) for usage, security
notes and the required trusted proxy setting.

## License

[MIT](LICENSE)
