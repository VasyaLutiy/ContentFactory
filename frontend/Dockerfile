FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_CONTENT_FACTORY_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_CONTENT_FACTORY_API_BASE_URL=${NEXT_PUBLIC_CONTENT_FACTORY_API_BASE_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup -S contentfactory && adduser -S contentfactory -G contentfactory

COPY --from=builder --chown=contentfactory:contentfactory /app/.next ./.next
COPY --from=builder --chown=contentfactory:contentfactory /app/package.json ./package.json
COPY --from=builder --chown=contentfactory:contentfactory /app/package-lock.json ./package-lock.json
COPY --from=deps --chown=contentfactory:contentfactory /app/node_modules ./node_modules

USER contentfactory

EXPOSE 3000

CMD ["npm", "run", "start"]
