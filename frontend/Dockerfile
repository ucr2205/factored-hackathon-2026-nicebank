ARG VITE_API_URL=http://localhost:8081
ARG VITE_OIDC_AUTHORITY=http://localhost:8080/realms/latam-bank
ARG VITE_JAEGER_URL=http://localhost:16686

FROM node:22-alpine AS build
ARG VITE_API_URL
ARG VITE_OIDC_AUTHORITY
ARG VITE_JAEGER_URL
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ARG VITE_API_URL
ARG VITE_OIDC_AUTHORITY
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/security-headers.conf
# The CSP may only connect to the origins the bundle was built against.
RUN origin() { echo "$1" | sed -E 's#^(https?://[^/]+).*#\1#'; } \
 && sed -i "s#__CONNECT_SRC__#$(origin "$VITE_API_URL") $(origin "$VITE_OIDC_AUTHORITY")#" /etc/nginx/security-headers.conf \
 && ! grep -q __CONNECT_SRC__ /etc/nginx/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
