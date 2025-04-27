FROM nginx:alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf

COPY ./ssl/cert.pem /etc/nginx/ssl/cert.pem
COPY ./ssl/key.pem /etc/nginx/ssl/key.pem

EXPOSE 80