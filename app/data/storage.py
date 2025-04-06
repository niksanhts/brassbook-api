from minio import Minio
from app.config import settings  # Исправлен импорт

class S3Storage:
    def __init__(self):
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT.split('://')[-1].split('/')[0],
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE  # Использование настройки
        )
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Гарантирует существование бакета"""
        if not self.client.bucket_exists(settings.MINIO_BUCKET_NAME):
            self.client.make_bucket(settings.MINIO_BUCKET_NAME)

    def upload_file(self, bucket: str, object_name: str, file_data):
        self._ensure_bucket_exists()  # Двойная проверка
        self.client.put_object(
            bucket_name=bucket,
            object_name=object_name,
            data=file_data,
            length=len(file_data))