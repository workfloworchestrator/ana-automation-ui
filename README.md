# nsi-mgmt-info

The NSI Management Info portal is a shared OIDC-authenticated landing page that
provides browser access to the UI endpoints of the NSI automation stack. It
serves a static HTML page with links to each application, and uses a shared
nginx ingress with path-based routing and oauth2-proxy for authentication.

The portal runs alongside the existing per-application mTLS ingresses, which
remain unchanged for machine-to-machine API access. Each application gets its
own path prefix on the portal ingress (e.g. `/dds-proxy/`, `/aura/`), and the
ingress rewrites the path before forwarding to the backend service.

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

The portal sits in front of the existing NSI applications and provides
OIDC-authenticated browser access to their UI endpoints:

```
Browser
  │
  ├── https://mgmt-info.dev.automation.surf.net/
  │     └── oauth2-proxy (OIDC) → nsi-mgmt-info (landing page)
  │
  ├── https://mgmt-info.dev.automation.surf.net/dds-proxy/
  │     └── oauth2-proxy (OIDC) → nsi-dds-proxy (rewrite /dds-proxy/… → /…)
  │
  ├── https://mgmt-info.dev.automation.surf.net/aura/
  │     └── oauth2-proxy (OIDC) → nsi-aura (rewrite /aura/… → /…)
  │
  └── ...
```

The existing mTLS ingresses continue to serve API traffic on their original
hostnames (e.g. `dds-proxy.dev.automation.surf.net`).

## Prerequisites

- Docker (for building the container image)
- A Kubernetes cluster with nginx ingress controller
- oauth2-proxy deployed for OIDC authentication
- cert-manager for TLS certificate provisioning

## Running Locally

### With Docker

Build and run the container:

```bash
docker build -t nsi-mgmt-info .
docker run --rm -p 8080:8080 nsi-mgmt-info
```

Then open http://localhost:8080 in your browser.

A pre-built image is available on the GitHub Container Registry:

```
ghcr.io/workfloworchestrator/nsi-mgmt-info:main
```

### With Helm chart

Install the chart with a custom values file:

```shell
helm upgrade --install --namespace development \
  --values values.yaml nsi-mgmt-info chart
```

Example `values.yaml`:

```yaml
image:
  repository: ghcr.io/workfloworchestrator/nsi-mgmt-info
  tag: main
ingress:
  enabled: true
  className: nginx-development
  host: mgmt-info.dev.automation.surf.net
  annotations:
    cert-manager.io/issuer: harica
    nginx.ingress.kubernetes.io/auth-url: "http://oauth2-proxy.development.svc.cluster.local/oauth2/auth"
    nginx.ingress.kubernetes.io/auth-signin: "https://mgmt-info.dev.automation.surf.net/oauth2/start?rd=$escaped_request_uri"
    nginx.ingress.kubernetes.io/auth-response-headers: "X-Auth-Request-User,X-Auth-Request-Email"
  tls:
    - secretName: tls-mgmt-info.dev.automation.surf.net
      hosts:
        - mgmt-info.dev.automation.surf.net
backends:
  - name: dds-proxy
    serviceName: development-nsi-dds-proxy
    servicePort: 80
```

## Backend Routing

Each backend application is exposed under a path prefix on the portal ingress.
The prefix is stripped before forwarding to the backend service, so applications
do not need to be aware of their path prefix.

Each backend gets its own Ingress resource because the nginx ingress controller
applies `rewrite-target` at the Ingress level, not per-path.

To add a new backend, add an entry to the `backends` list in `values.yaml`:

```yaml
backends:
  - name: my-app
    serviceName: development-my-app
    servicePort: 80
```

This creates an Ingress that routes `/my-app/(.*)` to the backend service with
the prefix stripped.

### Preserving the path prefix

Some backends already include the path prefix in their routes (e.g. DDS serves
all endpoints under `/dds/`). For these, set `rewriteTarget` to preserve the
prefix instead of stripping it:

```yaml
backends:
  - name: dds
    serviceName: development-nsi-dds
    servicePort: 80
    rewriteTarget: "/dds/$1"
```

### Per-backend annotations

Backends can specify additional annotations that are merged with the shared
ingress annotations. This is useful for server-rendered applications (like Play
or Rails apps) whose HTML contains absolute paths that need rewriting. For
example, Safnari uses nginx `sub_filter` to rewrite paths in HTML responses:

```yaml
backends:
  - name: safnari
    serviceName: development-nsi-safnari
    servicePort: 80
    annotations:
      nginx.ingress.kubernetes.io/configuration-snippet: |
        sub_filter_once off;
        sub_filter_types text/html;
        sub_filter 'href="/' 'href="/safnari/';
        sub_filter 'src="/' 'src="/safnari/';
        proxy_set_header Accept-Encoding "";
```

This approach works well for applications with simple server-rendered HTML (no
AJAX or JavaScript-generated URLs). Applications with JavaScript-driven UIs
(like FastAPI's Swagger docs) should use their framework's root path support
instead.
