# ==============================================================================
# AHONIX Frontend — Production Multi-stage Dockerfile
# ==============================================================================

# --- Stage 1: Build bundle ---
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json yarn.lock* package-lock.json* ./

# Install dependencies
RUN yarn install --frozen-lockfile || npm install

COPY . .

# Build argument for backend URL
ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Build optimized production bundle
RUN npm run build

# --- Stage 2: Serve static files with Nginx ---
FROM nginx:alpine

# Copy built assets to Nginx web root
COPY --from=builder /app/build /usr/share/nginx/html

# Copy SPA Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
