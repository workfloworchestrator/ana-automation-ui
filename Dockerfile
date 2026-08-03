# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89
#
# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:c89d95ee4e55a777beb40578b6019791410a375c2f2bceeb091b3be5f659b048 AS build
WORKDIR /app
COPY pyproject.toml ./
COPY app app
RUN uv build --no-cache --wheel --out-dir dist

# Final stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:c89d95ee4e55a777beb40578b6019791410a375c2f2bceeb091b3be5f659b048
COPY --from=build /app/dist/*.whl /tmp/
RUN uv pip install --system --no-cache /tmp/*.whl && rm /tmp/*.whl
RUN addgroup -g 1000 portal && adduser -D -u 1000 -G portal portal
USER portal
WORKDIR /home/portal
EXPOSE 8080/tcp
CMD ["ana-automation-ui"]
