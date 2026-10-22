# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#
# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:1fd17509ae6051e6cad9dc1b83705483c0b24a15740b3c4d230b6b6f2e2a0241 AS build
ARG VERSION
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}
WORKDIR /app
COPY pyproject.toml ./
COPY app app
RUN uv build --no-cache --wheel --out-dir dist

# Final stage
FROM ghcr.io/astral-sh/uv:python3.13-alpine@sha256:1fd17509ae6051e6cad9dc1b83705483c0b24a15740b3c4d230b6b6f2e2a0241
COPY --from=build /app/dist/*.whl /tmp/
RUN uv pip install --system --no-cache /tmp/*.whl && rm /tmp/*.whl
RUN addgroup -g 1000 portal && adduser -D -u 1000 -G portal portal
USER portal
WORKDIR /home/portal
EXPOSE 8080/tcp
CMD ["ana-automation-ui"]
