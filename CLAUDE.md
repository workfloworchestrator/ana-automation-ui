# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ANA Automation UI is a shared OIDC-authenticated portal that provides browser access to the UI endpoints of the NSI automation stack. It serves a static HTML landing page via nginx, with links to each application. Part of the ANA-GRAM project for federated network automation across research institutions.

The portal runs on its own hostname (`mgmt-info.dev.automation.surf.net`) alongside the existing per-application mTLS ingresses, which remain unchanged for machine-to-machine API access.

## Commands

```bash
# Build the container image
docker build -t ana-automation-ui .

# Run locally
docker run --rm -p 8080:8080 ana-automation-ui

# Render Helm templates for verification
helm template test chart/

# Render with custom values
helm template test chart/ --values values.yaml
```

## Architecture

**Static HTML site served by nginx:1-alpine** with a Helm chart for Kubernetes deployment:

- **`site/index.html`** — Landing page with card-based layout linking to each NSI application
- **`nginx.conf`** — Serves static site on port 8080 with `/health` endpoint
- **`Dockerfile`** — nginx:1-alpine based, runs as non-root user
- **`chart/`** — Helm chart with:
  - **`templates/deployment.yaml`** — Deploys the nginx container with health probes
  - **`templates/service.yaml`** — ClusterIP service port 80 → 8080
  - **`templates/ingress.yaml`** — Two types of Ingress resources:
    1. Main ingress for the landing page at path `/`
    2. Per-backend ingresses iterated from `.Values.backends` with `rewrite-target` to strip path prefixes

## Key Design Decisions

- Each backend gets its own Ingress resource because nginx ingress `rewrite-target` applies per-Ingress, not per-path
- Backend path prefixes are stripped by default (e.g. `/dds-proxy/docs` → `/docs`), but can be preserved via `rewriteTarget` for apps that include the prefix in their routes (e.g. DDS serves at `/dds/`)
- Backends support optional per-backend `annotations` for cases like server-rendered apps that need nginx `sub_filter` response rewriting (e.g. Safnari's Play-generated absolute paths are rewritten to include the `/safnari/` prefix)
- oauth2-proxy annotations are set on all ingresses (main + backends) via shared `.Values.ingress.annotations`
- Separate hostname from existing mTLS ingresses avoids TLS-level conflict (`auth-tls-verify-client` is a server-level nginx directive that applies to the entire hostname)
