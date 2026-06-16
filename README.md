# ana-automation-ui

The ANA Automation UI portal is a shared OIDC-authenticated landing page that
provides browser access to the UI endpoints of the NSI automation stack. It is a
FastAPI application that renders a group-aware portal: each application is shown as
a card whose link is enabled only for users whose group grants access. Users who
are in neither group see the greyed-out cards and a form to request access by email.

The portal sits behind oauth2-proxy, which authenticates the user and forwards
their identity and group membership (`X-Auth-Request-User`, `-Email`, `-Groups`).

## Project ANA-GRAM

This software is being developed by the
[Advanced North-Atlantic Consortium](https://www.anaeng.global/),
a cooperation between National Education and Research Networks (NRENs) and
research partners to provide network connectivity for research and education
across the North-Atlantic, as part of the ANA-GRAM (ANA Global Resource
Aggregation Method) project.

The goal of the ANA-GRAM project is to federate the ANA trans-Atlantic links
through [Network Service Interface (NSI)](https://ogf.org/documents/GFD.237.pdf)-based
automation. This will enable the automated provisioning of L2 circuits spanning
different domains between research parties on other sides of the Atlantic. The
ANA-GRAM project is spearheaded by the ANA Platform & Requirements Working
Group, under guidance of the ANA Engineering and ANA Planning Groups.

<p align="center" width="50%">
    <img width="50%" src="/artwork/ana-logo-scaled-ab2.png">
</p>

## Architecture

The portal is a FastAPI app served by uvicorn. oauth2-proxy authenticates browser
users and forwards `X-Auth-Request-*` headers; the app derives the user's role from
their group membership and renders the portal accordingly.

```
Browser
  │  https://<portal-host>/
  └── oauth2-proxy (OIDC) ──► ana-automation-ui (FastAPI portal)
            └── forwards X-Auth-Request-User / -Email / -Groups
```

Backend applications are reached through path prefixes on the portal host (e.g.
`/aura/`, `/dds/`), each routed to its service with the prefix stripped. The
existing per-application mTLS ingresses continue to serve API traffic on their own
hostnames, unchanged.

### Routing is up to you

The chart deploys the app (Deployment, Service) and its configuration, but **how
you route traffic and enforce auth is your choice**. Both chart-provided routing
templates are disabled by default; pick one of:

1. **Chart nginx Ingress** — set `ingress.enabled=true` and configure `ingress`
   plus `backends` (per-backend Ingresses with path rewriting and oauth2-proxy
   auth annotations).
2. **Chart Gateway API HTTPRoute** — set `httpRoute.enabled=true` and configure
   `httpRoute.routes`.
3. **Completely external configuration** — manage routing, oauth2-proxy auth, path
   rewrites and group enforcement outside the chart, with whatever ingress controller
   or gateway you run (for example an nginx or Traefik gateway with oauth2-proxy
   forward-auth).

Whichever you choose, oauth2-proxy must forward `X-Auth-Request-Groups`, and the
routing layer should strip inbound `X-Auth-Request-*` headers from the client
before oauth2-proxy sets them, so they cannot be spoofed.

## Access model

| Group | Access |
|-------|--------|
| `operators` | read-write — may open every app |
| `users` | read-only — may open the non-operator apps |
| neither | may only load the portal to see greyed cards and request access |

The portal greys out cards a user cannot open and shows a `USERS` / `OPERATORS`
badge per app. **This greying is cosmetic** — the real gate is the routing layer
(e.g. oauth2-proxy `allowed_groups`), which returns 403 if a user opens a restricted
app directly. Keep each app's `requiredGroup` in step with the routing enforcement.

## Configuration

The app reads settings from environment variables, or from a local
`ana-automation-ui.env` file (see `ana-automation-ui.env.example`). Real environment
variables take precedence over the file.

| Variable | Purpose |
|----------|---------|
| `HOST`, `PORT` | uvicorn bind address (default `0.0.0.0:8080`) |
| `USERS_GROUP`, `OPERATORS_GROUP` | OIDC group names (default `users` / `operators`) |
| `APPS_CONFIG_PATH` | apps JSON path (default `/config/apps.json`; falls back to the bundled list) |
| `EMAIL_ENABLED` | enable the access-request email feature |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` | SMTP relay (`SMTP_SECURITY`: `none` / `starttls` / `tls`) |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | optional SMTP auth |
| `ACCESS_REQUEST_RECIPIENT` | where access requests are sent |
| `ACCESS_REQUEST_FROM` | fixed sender address |
| `ACCESS_REQUEST_FROM_USER` | send From the requester's email instead (default `false`) |

The portal app list is configured via `portal.apps` (rendered into a ConfigMap
mounted at `/config/apps.json`); when empty, the image's bundled default list is
used. Each entry: `name`, `description`, `url`, `requiredGroup` (empty = any
authenticated user), `comingSoon`.

## Running locally

With uv:

```bash
uv sync
uv run ana-automation-ui          # serves http://localhost:8080
```

Simulate oauth2-proxy headers to see the group-aware rendering:

```bash
curl -s http://localhost:8080/ -H 'X-Auth-Request-Groups: operators'
```

With Docker (two-stage uv wheel build):

```bash
docker build -t ana-automation-ui .
docker run --rm -p 8080:8080 ana-automation-ui
```

A pre-built image is published to the GitHub Container Registry:

```
ghcr.io/workfloworchestrator/ana-automation-ui:main
```

### With the Helm chart

```shell
helm upgrade --install --namespace development \
  --values values.yaml ana-automation-ui chart
```

Example `values.yaml`:

```yaml
image:
  repository: ghcr.io/workfloworchestrator/ana-automation-ui
  tag: main
groups:
  users: users
  operators: operators
portal:
  apps:
    - name: AuRA
      description: NSI user provider agent for managing reservations.
      url: /aura/
      requiredGroup: operators
    - name: DDS
      description: Topology document registry.
      url: /dds/portal
email:
  enabled: true
  recipient: ops@example.org
  from: portal@example.org
  smtp:
    host: mailrelay.internal
    port: 25
# Routing: enable one of ingress / httpRoute, or configure it externally (see above).
```

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```
