# ── Stage 1: Build Angular app ────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app

# Cache dependency layer separately
COPY package*.json ./
RUN npm ci --legacy-peer-deps

# Compile production build
COPY . .
RUN npm run build -- --configuration production

# ── Stage 2: Serve browser bundle with nginx ──────────────────────────────
FROM nginx:stable-alpine
WORKDIR /usr/share/nginx/html

# Copy only the browser-side static files
COPY --from=build /app/dist/urlShortner-ui/browser .

# SPA routing config: unknown paths fall back to index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/ | grep -q '<app-root' || exit 1
