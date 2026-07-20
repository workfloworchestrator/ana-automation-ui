# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89
#
# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:cb6afa05152bd54d7ef164031358075a508cbd5999d0b4bf2fbb22ecf503f038 AS build
WORKDIR /app
COPY pyproject.toml ./
COPY app app
RUN uv build --no-cache --wheel --out-dir dist

# Final stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:cb6afa05152bd54d7ef164031358075a508cbd5999d0b4bf2fbb22ecf503f038
COPY --from=build /app/dist/*.whl /tmp/
RUN uv pip install --system --no-cache /tmp/*.whl && rm /tmp/*.whl
RUN addgroup -g 1000 portal && adduser -D -u 1000 -G portal portal
USER portal
WORKDIR /home/portal
EXPOSE 8080/tcp
CMD ["ana-automation-ui"]
