# Server deployment

The landing page is served directly on `dobriy-ai-k8s` at IPv4 `46.225.13.35`. Both `fundings.wiki` and `www.fundings.wiki` point here. The latter redirects to the canonical HTTPS domain.

This node is deliberately excluded from the Kubernetes ingress DaemonSet. The dedicated `shortlist-web` systemd service binds only this public IPv4 address on TCP ports 80 and 443. It does not change cluster scheduling, ingress, the existing load balancer or other sites. Caddy manages and renews the domain certificates through Let's Encrypt.

## Runtime paths

All application data lives on the attached workspace volume:

- `/srv/workspace/users/1000/shortlist` is the Git checkout.
- `/srv/workspace/users/1000/shortlist-runtime/bin/caddy` is the Caddy v2.11.9 binary from the official release, verified against the published SHA-512 checksum.
- `shortlist-runtime/releases/<commit>-<artifact-digest-prefix>/` contains immutable static releases. The original release uses its commit alone.
- `shortlist-runtime/current` is an atomically replaced symlink to the active release.
- `shortlist-runtime/Caddyfile` is the active copy of the tracked configuration.
- `shortlist-runtime/state/` holds private certificate data, Caddy state and its permission-restricted admin socket.

The service runs as `vanya`, with permission to bind low ports and write only to its state directory. The served root contains only built public assets. TLS state is outside that root and must never be committed.

## Publish a change

The normal path is to push or merge to `main`. The [CI and deployment workflow](../.github/workflows/ci-cd.yml) runs source and deployment tests, installs the pinned dependencies, builds once, and runs the browser suite. It uploads only the tested `dist/` archive, with a SHA-256 checksum. The deployment job downloads that exact artifact by ID and sends it to the restricted server receiver over SSH.

The `production` GitHub environment accepts only `main`, with no manual approval delay. Deployments are serialized. Superseded commits are skipped by the workflow and rejected again on the server. Source, build and browser failures prevent deployment. Fork pull requests run the credential-free source and deployment checks. The private company stylesheet means their full browser build needs a maintainer-owned branch.

The receiver validates file paths, types, size, checksum and commit, then switches the active symlink. Public HTTPS checks verify the release identity, HTML, CSS, JavaScript, a font and service health. A failed or interrupted server verification restores the previous release. The workflow performs an additional public smoke check from the GitHub runner.

### Credentials and server setup

- Repository secret `STYLE_DEPLOY_KEY` is a dedicated read-only deploy key for `semantic/interface-style` in GitLab. It has no write permission and no access to other projects.
- Environment secret `DEPLOY_SSH_KEY` is a separate key for this site's production deployment. Its authorized-key entry uses `restrict` and a forced command, `/usr/bin/python3 /usr/local/lib/shortlist/receive.py`. It cannot open a shell, forward ports, or use SFTP.
- Host keys are pinned in [.github/known_hosts](../.github/known_hosts). Credentials are passed only to the steps that need them, and temporary key files are removed before later steps.
- GitHub-hosted runners execute builds and pull-request code. No Actions runner is installed on the production server. No shared private-package cache is published.

The receiver is installed separately as a root-owned file. CI cannot replace it or change Caddy/systemd configuration. After reviewing and testing an intentional receiver change, update it on the server:

```sh
workspace-run python3 -m unittest discover -s tests -p 'test_*.py' -v
sudo install -m 755 deploy/receive.py /usr/local/lib/shortlist/receive.py
```

Private keys are held in GitHub Actions secrets. Revoke the corresponding GitLab deploy key or SSH authorized-key entry before replacing a credential. Do not copy a personal SSH key into CI.

### Manual fallback

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

The release script requires a clean checkout matching `origin/main`, checks the build revision, and sends the artifact through the same installed receiver as CI. Identical artifacts are safe to retry. Existing releases are preserved. Static content updates do not require a service restart.

For an intentional Caddy configuration change, validate it, copy it to the runtime path and reload the dedicated service. Install the systemd unit from `shortlist-web.service` on initial setup, then enable it. Do not start another process on these ports or enable the cluster ingress on this node while the service owns them.

## Verify and roll back

```sh
systemctl status shortlist-web --no-pager
curl --fail https://fundings.wiki/healthz
curl --fail https://fundings.wiki/release.json
curl -I https://www.fundings.wiki/
journalctl -u shortlist-web -n 30 --no-pager
```

Failed server verification rolls back automatically. To roll back manually, atomically point `current` to a retained release directory, then verify its public `release.json`. Revert the offending source commit on `main` as well so a later automatic deployment does not restore the change. Preserve previous releases until the replacement is verified. Certificates renew independently of application releases.

GitHub holds the source backup. The workspace volume is excluded from Hetzner server backups. Certificate state can be reissued, but any future irreplaceable runtime data will need an independent backup before being added.
