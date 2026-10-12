# Simple Cloudflare Tunnel for Home Assistant

A Home Assistant add-on that exposes Home Assistant through Cloudflare, without
opening ports. Everything is set up from its sidebar panel:

- **Permanent access** on your own hostname, such as `ha.example.com`. Paste a
  scoped Cloudflare API token, pick a hostname, click Set up: the add-on
  creates the tunnel and DNS record, and can remove them again.
- **Temporary access** on a random `trycloudflare.com` URL, no Cloudflare
  account needed. Tunnels expire after a duration you pick.

## Install

[![Add repository to your Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FZnuff%2Fha-simple-cf-tunnel)

Or manually: **Settings → Add-ons → Add-on store → ⋮ → Repositories**, add
`https://github.com/Znuff/ha-simple-cf-tunnel`, then install
**Simple Cloudflare Tunnel**.

Images are prebuilt for `amd64` and `aarch64` by GitHub Actions and published
to GitHub's container registry, so installs and updates only download them.

See [the add-on documentation](simple_cf_tunnel/DOCS.md) for usage, security
notes and the required trusted proxy setting.

## License

[MIT](LICENSE)
