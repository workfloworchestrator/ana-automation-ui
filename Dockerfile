# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89
#
# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:f09cc61ffc001f202701fdeae14dbdd50f6ca4cfcf248f41fd3234a302c8534f AS build
WORKDIR /app
COPY pyproject.toml ./
COPY app app
RUN uv build --no-cache --wheel --out-dir dist

# Final stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:f09cc61ffc001f202701fdeae14dbdd50f6ca4cfcf248f41fd3234a302c8534f
COPY --from=build /app/dist/*.whl /tmp/
RUN uv pip install --system --no-cache /tmp/*.whl && rm /tmp/*.whl
RUN addgroup -g 1000 portal && adduser -D -u 1000 -G portal portal
USER portal
WORKDIR /home/portal
EXPOSE 8080/tcp
CMD ["ana-automation-ui"]
