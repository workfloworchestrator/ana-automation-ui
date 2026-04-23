FROM nginx:1-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY site/ /usr/share/nginx/html/

EXPOSE 8080

RUN chown -R nginx:nginx /usr/share/nginx/html && \
    sed -i 's/listen\s*80;/listen 8080;/' /etc/nginx/conf.d/default.conf || true

USER nginx
