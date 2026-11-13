# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#
# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:f2d6278d0821c35881b010ddbf75825049661a98dbfdf61bbd1407e8dd544d00 AS build
ARG VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
WORKDIR /app
COPY pyproject.toml ./
COPY app app
RUN uv build --no-cache --wheel --out-dir dist

# Final stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:f2d6278d0821c35881b010ddbf75825049661a98dbfdf61bbd1407e8dd544d00
COPY --from=build /app/dist/*.whl /tmp/
RUN uv pip install --system --no-cache /tmp/*.whl && rm /tmp/*.whl
RUN addgroup -g 1000 portal && adduser -D -u 1000 -G portal portal
USER portal
WORKDIR /home/portal
EXPOSE 8080/tcp
CMD ["ana-automation-ui"]
