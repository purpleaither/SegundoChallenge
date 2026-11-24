# Frontend Next.js (build standalone)
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS build
WORKDIR /app
# Os rewrites do Next são fixados no build.
ARG BACKEND_URL=http://backend:8000
ARG STT_URL=http://stt:8002
ARG TTS_URL=http://tts:8001
ENV BACKEND_URL=$BACKEND_URL \
    STT_URL=$STT_URL \
    TTS_URL=$TTS_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]