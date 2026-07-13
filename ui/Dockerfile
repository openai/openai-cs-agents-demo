FROM node:20-alpine AS dependencies
WORKDIR /app
COPY ui/package.json ui/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY ui/ ./
ARG NEXT_PUBLIC_CHATKIT_DOMAIN_KEY
ARG NEXT_PUBLIC_AUTH_MODE=oidc
ARG NEXT_PUBLIC_DEFAULT_APP_SURFACE=support
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV NEXT_PUBLIC_CHATKIT_DOMAIN_KEY=$NEXT_PUBLIC_CHATKIT_DOMAIN_KEY \
    NEXT_PUBLIC_AUTH_MODE=$NEXT_PUBLIC_AUTH_MODE \
    NEXT_PUBLIC_DEFAULT_APP_SURFACE=$NEXT_PUBLIC_DEFAULT_APP_SURFACE \
    BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app ./
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
