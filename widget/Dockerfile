# Gomulebilir widget paketini uretir (widget.js + widget.css).
# Cikti nginx tarafindan /widget/ altinda servis edilir.
FROM node:22-alpine AS build

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.ts ./
COPY src ./src

RUN npm run build:embed

# Statik cikti — nginx bu asamadan kopyalar.
FROM alpine:3 AS dist
COPY --from=build /build/dist-embed /widget
