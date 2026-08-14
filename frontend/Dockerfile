# Build the static bundle, then serve it from nginx — no Node in the
# runtime image. VITE_API_URL defaults to a same-origin relative path
# (/api/v1) because nginx.conf proxies /api/ to the backend container, so
# the browser never needs the backend's real hostname and there's no CORS
# to configure for the containerized deployment.

FROM node:22-slim AS builder

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build


FROM nginx:alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1
