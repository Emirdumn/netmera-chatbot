# Gomulebilir widget paketini uretir (widget.js + widget.css).
# Cikti nginx tarafindan /widget/ altinda servis edilir.
FROM node:22-alpine AS build

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public

RUN npm run build:embed

# Statik cikti — Caddy /widget/* altinda servis eder.
FROM alpine:3 AS dist
COPY --from=build /build/dist-embed /widget
# Smoke test sayfasi: https://<host>/widget/embed-test.html
COPY --from=build /build/public/embed-test.html /widget/embed-test.html
