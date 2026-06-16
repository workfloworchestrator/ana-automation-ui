# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ANA Automation UI is a shared OIDC-authenticated portal that provides browser access to the UI endpoints of the NSI automation stack. It is a FastAPI application that renders a group-aware landing page: each application is shown as a card whose link is enabled only for users whose group grants access, and users who are in neither group see the greyed-out cards and a form to request access by email. Part of the ANA-GRAM project for federated network automation across research institutions.

The portal sits behind oauth2-proxy, which authenticates the user and forwards their identity and group membership via `X-Auth-Request-*` headers.

## Commands

```bash
# Install dependencies (creates .venv)
uv sync

# Run the app locally (reads ana-automation-ui.env if present)
uv run ana-automation-ui            # or: uv run uvicorn app.main:app --reload

# Lint, format check, type-check, test
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest

# Build the container image (two-stage uv wheel build)
docker build -t ana-automation-ui .

# Render Helm templates
helm template test chart/
```

## Architecture

**FastAPI app (`app/`), served by uvicorn**, with a Helm chart for Kubernetes deployment.

- **`app/main.py`** — FastAPI app: `GET /` (group-aware portal), `POST /request-access` (email an access request), `GET /health`; mounts `/static`; sets CSP + security headers; `run()` console entry point.
- **`app/config.py`** — `Settings` (pydantic-settings), read from the environment or `ana-automation-ui.env`.
- **`app/auth.py`** — parses `X-Auth-Request-User/Email/Groups` into `CurrentUser` + `Role` (operators ⊇ users) via the `get_current_user` dependency.
- **`app/apps.py`** — `AppCard`/`AppView`; loads the app list from `APPS_CONFIG_PATH` or the bundled `app/apps.json`; decides per-app access state and badge per role.
- **`app/mail.py`** — builds the access-request email (fixed From + requester Reply-To, CR/LF injection guard) and sends it via `aiosmtplib`.
- **`app/ratelimit.py`** — in-memory per-user rate limiter for the request-access endpoint.
- **`app/templates/`, `app/static/`** — Jinja2 templates and static assets (logo, `app.js`), bundled into the wheel.
- **`chart/`** — Helm chart: `deployment.yaml`, `service.yaml`, `configmap-apps.yaml` (renders `portal.apps`), `secret-provider-class.yaml` (Azure Key Vault via the Secrets Store CSI driver), and the optional `ingress.yaml` / `httproute.yaml` routing templates.

## Routing and authentication

The chart deploys the app (Deployment + Service) and its configuration, but **how you route traffic and enforce auth is up to the deployment**. Both chart-provided routing templates are disabled by default; choose one of:

1. **Chart nginx Ingress** — `ingress.enabled=true` plus `ingress` and `backends` (per-backend Ingresses with path rewriting and oauth2-proxy auth annotations).
2. **Chart Gateway API HTTPRoute** — `httpRoute.enabled=true` plus `httpRoute.routes`.
3. **Completely external configuration** — routing, oauth2-proxy auth, path rewrites and group enforcement maintained outside the chart, using whatever ingress controller or gateway the operator runs.

In all cases oauth2-proxy authenticates the user and forwards `X-Auth-Request-User/Email/Groups`. Group enforcement (which group may open which app) is done at the routing layer — the portal's card greying mirrors it but is **not** the gate.

## Key Design Decisions

- **Two-group model**: `users` = read-only, `operators` = read-write (a superset). A user in neither group sees only greyed cards and the access-request form; the routing layer returns 403 if they open a restricted app directly.
- **Header trust boundary**: the app trusts `X-Auth-Request-*` for *display only*, never to grant a server-side action. The routing layer must strip these headers from client input before oauth2-proxy populates them (e.g. a header-stripping middleware on the ingress or gateway), so clients can't self-attest.
- **Apps as config**: the portal app list is data (`portal.apps` → ConfigMap, or the bundled default), so adding or retiring an app is a config change. Each app's `requiredGroup` mirrors the routing-layer enforcement and must agree with it.
- **CSP + security headers** are set by the app, so they apply regardless of the routing layer.
- The access-request email uses a fixed authenticated `From` with the requester in `Reply-To` for deliverability; `email.fromUser` opts into using the requester's own address as `From`.
