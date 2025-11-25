FROM node:21 AS base

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

RUN npm install -g pnpm

COPY package.json pnpm-lock.yaml ./

FROM base AS deps
ENV NODE_ENV=development
RUN pnpm install --frozen-lockfile

FROM base AS builder
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm run build

FROM base AS prod-deps
ENV NODE_ENV=production
RUN pnpm install --frozen-lockfile --prod

FROM base AS dev
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["pnpm", "exec", "next", "dev", "--turbo", "--hostname", "0.0.0.0"]

FROM node:21-slim AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app

COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "--hostname", "0.0.0.0"]
