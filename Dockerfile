FROM node:22-alpine
WORKDIR /app
COPY api/package.json api/package-lock.json ./
RUN npm ci --omit=dev
COPY api/*.js ./
COPY api/*.sql ./
EXPOSE 3000
CMD ["node", "server.js"]
