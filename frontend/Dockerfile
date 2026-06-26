# =============================================================================
# RetailFlow AI — Frontend Dockerfile
# =============================================================================
# Multi-stage build:
#   1. base       → Node.js base with dependencies installed
#   2. development → Hot reload dev server
#   3. builder    → Production build
#   4. production → Minimal production runtime image
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Base — Node.js with dependencies
# ---------------------------------------------------------------------------
FROM node:20-alpine AS base

# Install system dependencies
RUN apk add --no-cache libc6-compat curl

WORKDIR /app

# Copy dependency manifests
COPY package.json package-lock.json ./

# ---------------------------------------------------------------------------
# Stage 2: Development — Hot reload
# ---------------------------------------------------------------------------
FROM base AS development

# Install ALL dependencies (including devDependencies)
RUN npm ci

COPY . .

# Expose Next.js dev port
EXPOSE 3000

ENV NODE_ENV=development
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "dev"]

# ---------------------------------------------------------------------------
# Stage 3: Builder — Production build
# ---------------------------------------------------------------------------
FROM base AS builder

# Install ALL dependencies for build
RUN npm ci

COPY . .

# Disable Next.js telemetry
ENV NEXT_TELEMETRY_DISABLED=1

# Build the application
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 4: Production — Minimal runtime
# ---------------------------------------------------------------------------
FROM node:20-alpine AS production

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy only necessary files from builder
COPY --from=builder /app/public ./public

# Next.js standalone output
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
