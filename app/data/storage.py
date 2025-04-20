import logging
import uuid
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from app.config import (MINIO_ACCESS_KEY, MINIO_BUCKET_NAME, MINIO_ENDPOINT, MINIO_SECRET_KEY, MAX_FILE_SIZE)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize MinIO client
try:
    minio_client = Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,  # Enable HTTPS by default
    )
    logger.info("MinIO client initialized successfully for endpoint: %s", MINIO_ENDPOINT)
except Exception as e:
    logger.error("Failed to initialize MinIO client: %s", str(e))
    raise RuntimeError(f"Failed to initialize MinIO client: {str(e)}")

# Check and create bucket if it doesn't exist
try:
    if not minio_client.bucket_exists(MINIO_BUCKET_NAME):
        minio_client.make_bucket(MINIO_BUCKET_NAME)
        logger.info("Bucket created: %s", MINIO_BUCKET_NAME)
    else:
        logger.debug("Bucket already exists: %s", MINIO_BUCKET_NAME)
except S3Error as e:
    logger.error("Failed to check or create bucket %s: %s", MINIO_BUCKET_NAME, str(e))
    raise RuntimeError(f"Failed to initialize MinIO bucket: {str(e)}")


def get_minio_client() -> Minio:
    """
    Retrieve the initialized MinIO client.

    Returns:
        Minio: Configured MinIO client instance.

    Raises:
        RuntimeError: If MinIO client is not initialized.
    """
    logger.debug("Providing MinIO client instance")
    if minio_client is None:
        logger.error("MinIO client is not initialized")
        raise RuntimeError("MinIO client is not initialized")
    return minio_client


def save_file(file: UploadFile) -> str:
    """
    Save an uploaded file to MinIO and return its object name.

    Args:
        file: Uploaded file to save.

    Returns:
        str: Object name of the saved file in MinIO.

    Raises:
        HTTPException: If file is invalid, too large, or upload fails.
    """
    logger.info("Saving file: %s", file.filename)
    
    if not file.filename:
        logger.warning("No filename provided")
        raise HTTPException(status_code=400, detail="No filename provided")
    
    if file.size > MAX_FILE_SIZE:
        logger.warning("File too large: %s (size: %d bytes)", file.filename, file.size)
        raise HTTPException(
            status_code=413, detail=f"File size exceeds limit of {MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    # Sanitize filename to prevent path injection
    safe_filename = file.filename.replace("/", "_").replace("\\", "_")
    object_name = f"{uuid.uuid4()}_{safe_filename}"

    try:
        with file.file as f:
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
            minio_client.put_object(
                bucket_name=MINIO_BUCKET_NAME,
                object_name=object_name,
                data=f,
                length=file_size,
                part_size=10 * 1024 * 1024,  # 10MB part size for multipart upload
                content_type=file.content_type or "application/octet-stream",
            )
        logger.info("File saved successfully: %s as %s", file.filename, object_name)
        return object_name
    except S3Error as e:
        logger.error("Failed to save file %s to MinIO: %s", file.filename, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error while saving file %s: %s", file.filename, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


def get_file_url(filename: str, expires: int = 3600) -> str:
    """
    Generate a presigned URL for accessing a file in MinIO.

    Args:
        filename: Object name of the file in MinIO.
        expires: URL expiration time in seconds (default: 1 hour).

    Returns:
        str: Presigned URL for accessing the file.

    Raises:
        HTTPException: If URL generation fails.
    """
    logger.debug("Generating presigned URL for file: %s", filename)
    try:
        url = minio_client.presigned_get_object(
            bucket_name=MINIO_BUCKET_NAME,
            object_name=filename,
            expires=expires
        )
        logger.info("Presigned URL generated for file: %s", filename)
        return url
    except S3Error as e:
        logger.error("Failed to generate presigned URL for %s: %s", filename, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate file URL: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error while generating URL for %s: %s", filename, str(e))
        raise HTTPException(status_code=500, detail="Internal server error")