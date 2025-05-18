#!/bin/sh
set -e

# IF THIS SCRIPT FAILS - SET LF INSTEAD OF CRLF

# Install curl if not present
if ! command -v curl &> /dev/null; then
  echo "curl not found, installing..."
  apk add --no-cache curl
fi

minio server /data --console-address ":9001" &

echo "Waiting for MinIO to start..."
while ! curl -s "http://$MINIO_ENDPOINT/minio/health/live" >/dev/null; do
  sleep 1
done
echo "MinIO is up!"

echo "Setting up MinIO with alias 'local' at http://$MINIO_ENDPOINT"
mc alias set local "http://$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb --ignore-existing "local/$MINIO_BUCKET_NAME"
mc anonymous set download "local/$MINIO_BUCKET_NAME"
echo "MinIO bucket '$MINIO_BUCKET_NAME' configured successfully!"

wait
