import logging
from datetime import timedelta
from typing import BinaryIO, Optional

from fastapi import HTTPException
from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)


class S3Repository:
    def __init__(self):
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
        )

    async def upload_file(
        self,
        bucket: str,
        object_name: str,
        file_data: BinaryIO,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Загрузка файла в S3"""
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)

            self.client.put_object(
                bucket_name=bucket,
                object_name=object_name,
                data=file_data,
                length=-1,
                content_type=content_type,
            )
            return object_name
        except S3Error as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(status_code=500, detail="File upload failed")

    async def get_file_url(
        self, bucket: str, object_name: str, expires: int = 3600
    ) -> Optional[str]:
        """Генерация временной ссылки на файл"""
        try:
            return self.client.presigned_get_object(
                bucket, object_name, expires=timedelta(seconds=expires)
            )
        except S3Error:
            return None

    async def delete_file(self, bucket: str, object_name: str) -> bool:
        """Удаление файла"""
        try:
            self.client.remove_object(bucket, object_name)
            return True
        except S3Error:
            return False


# Dependency для внедрения
def get_s3_repo() -> S3Repository:
    return S3Repository()
