# ─── Frontend Dockerfile ─────────────────────────────────────────────────────
# AI Revenue Recovery — Next.js 14 container (multi-stage build)
#
# Build:
#   docker build \
#     --build-arg NEXT_PUBLIC_API_URL=http://backend:8000 \
#     -t ai-revenue-frontend ./frontend
#
# Run:  docker run -p 3000:3000 ai-revenue-frontend
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Dependencies ─────────────────────────────────────────────────────
FROM node:18-alpine AS deps

# Install libc6-compat for Alpine compatibility with native Node modules
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copy package manifests only (better layer caching)
COPY package.json package-lock.json* ./

RUN npm ci --prefer-offline


# ── Stage 2: Builder ──────────────────────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# Accept the API URL as a build arg (default: backend service name in Compose)
ARG NEXT_PUBLIC_API_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Re-use the installed node_modules from the deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy the rest of the source code
COPY . .

# Build the optimised Next.js production bundle
RUN npm run build


# ── Stage 3: Runner ───────────────────────────────────────────────────────────
FROM node:18-alpine AS runner

WORKDIR /app

# Reduce image attack surface: production-only runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

# Create a non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Copy only the artefacts needed to run Next.js in standalone mode
# (falls back to standard .next if standalone not enabled in next.config.js)
COPY --from=builder /app/public          ./public
COPY --from=builder /app/.next           ./.next
COPY --from=builder /app/node_modules    ./node_modules
COPY --from=builder /app/package.json    ./package.json
COPY --from=builder /app/next.config.js  ./next.config.js

RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["npm", "start"]
