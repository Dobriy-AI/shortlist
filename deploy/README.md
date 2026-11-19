# Server deployment

The landing page is served directly on `dobriy-ai-k8s` at IPv4 `46.225.13.35`. Both `fundings.wiki` and `www.fundings.wiki` point here. The latter redirects to the canonical HTTPS domain.

This node is deliberately excluded from the Kubernetes ingress DaemonSet. The dedicated `shortlist-web` systemd service binds only this public IPv4 address on TCP ports 80 and 443. It does not change cluster scheduling, ingress, the existing load balancer or other sites. Caddy manages and renews the domain certificates through Let's Encrypt.

## Runtime paths

All application data lives on the attached workspace volume:

- `/srv/workspace/users/1000/shortlist` is the Git checkout.
- `/srv/workspace/users/1000/shortlist-runtime/bin/caddy` is the Caddy v2.11.9 binary from the official release, verified against the published SHA-512 checksum.
- `shortlist-runtime/releases/<commit>/` contains immutable static releases.
- `shortlist-runtime/current` is an atomically replaced symlink to the active release.
- `shortlist-runtime/Caddyfile` is the active copy of the tracked configuration.
- `shortlist-runtime/state/` holds private certificate data, Caddy state and its permission-restricted admin socket.

The service runs as `vanya`, with permission to bind low ports and write only to its state directory. The served root contains only built public assets. TLS state is outside that root and must never be committed.

## Publish a change

Run checks and browser validation, then commit and push the source. Build again after committing so `release.json` records the deployed revision.

```sh
workspace-run --check
workspace-run npm ci
workspace-run npm run check
workspace-run npm run test:browser
# Commit and push the reviewed source.
workspace-run npm run build
python3 deploy/release.py
```

The release script requires a clean checkout matching `origin/main`, checks the build revision, refuses to overwrite existing releases, and changes only the content symlink. Static content updates do not require a service restart.

For an intentional Caddy configuration change, validate it, copy it to the runtime path and reload the dedicated service. Install the systemd unit from `shortlist-web.service` on initial setup, then enable it. Do not start another process on these ports or enable the cluster ingress on this node while the service owns them.

## Verify and roll back

```sh
systemctl status shortlist-web --no-pager
curl --fail https://fundings.wiki/healthz
curl --fail https://fundings.wiki/release.json
curl -I https://www.fundings.wiki/
journalctl -u shortlist-web -n 30 --no-pager
```

To roll back, atomically point `current` to a retained release directory. Preserve previous releases until the replacement is verified. Certificates renew independently of application releases.

GitHub holds the source backup. The workspace volume is excluded from Hetzner server backups. Certificate state can be reissued, but any future irreplaceable runtime data will need an independent backup before being added.
