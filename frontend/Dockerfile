# ─── Frontend Dockerfile ─────────────────────────────────────────────────────
# AI Revenue Recovery — Next.js 14 container (3-stage Alpine build)
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

# Copy package manifests only for optimal layer caching
COPY package.json package-lock.json* ./

RUN npm ci --prefer-offline


# ── Stage 2: Builder ──────────────────────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# Accept API URL and Demo controls as build arguments
ARG NEXT_PUBLIC_API_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG NEXT_PUBLIC_ENABLE_DEMO_CONTROLS=true
ENV NEXT_PUBLIC_ENABLE_DEMO_CONTROLS=$NEXT_PUBLIC_ENABLE_DEMO_CONTROLS

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy application source code
COPY . .

# Build standalone Next.js bundle
RUN npm run build


# ── Stage 3: Runner ───────────────────────────────────────────────────────────
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Create a non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Copy static public assets
COPY --from=builder /app/public ./public

# Copy only the standalone server and traced output (brings image size under 150 MB)
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

# Launch the lightweight standalone Node server directly without npm overhead
CMD ["node", "server.js"]
