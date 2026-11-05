# Web image: the built frontend (static files) served by Caddy, which also proxies /api
# to the API and applies per-IP rate limits. Build context: the repository root.
#
#   docker build -f deploy/web/Dockerfile -t documind-web .

FROM node:22-bookworm-slim AS frontend
WORKDIR /src
# package.json asks for npm 11 (npm 10 cannot resolve vitest's optional peers)
RUN npm install -g npm@11.21.2
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# the bundle calls the API under this path; Caddy routes it to the API service
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# Caddy with the rate-limit plugin (not part of the standard build), pinned
FROM caddy:2.11-builder-alpine AS caddy
RUN xcaddy build v2.11.7 \
      --with github.com/mholt/caddy-ratelimit@v0.1.1-0.20260612195517-5625512f24f6

FROM caddy:2.11-alpine
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
# bind ports 80 and 443 without root
RUN apk add --no-cache libcap \
 && setcap cap_net_bind_service=+ep /usr/bin/caddy \
 && addgroup -S -g 10002 web && adduser -S -D -H -u 10002 -G web web \
 && mkdir -p /data/caddy /config/caddy && chown -R web:web /data /config
COPY deploy/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /src/dist /srv
USER web
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:2019/config/"]
