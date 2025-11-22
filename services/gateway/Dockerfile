# base stage
FROM oven/bun:slim AS base
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production
COPY . .

# deps stage
FROM oven/bun:slim AS deps
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# migrator stage
FROM oven/bun:slim AS migrator
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package.json bun.lock ./
COPY drizzle.config.ts ./
COPY src/platform/database ./src/platform/database
COPY migrations ./migrations

CMD ["bun", "run", "db:migrate"]

# gateway stage
FROM base AS gateway
ENV NODE_ENV=production
ENV PORT=8080
EXPOSE 8080
CMD ["bun", "run", "start:gateway"]

# worker stage
FROM base AS worker
ENV NODE_ENV=production
CMD ["bun", "run", "start:worker"]