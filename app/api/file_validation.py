import logging
from typing import Optional

import magic
from fastapi import HTTPException, UploadFile
from app.config import MAX_FILE_SIZE

# Configure logging
logger = logging.getLogger(__name__)

# Allowed file extensions and corresponding MIME types
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "mp3", "wav"}
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
}

def allowed_file(filename: Optional[str]) -> bool:
    """
    Check if the file extension is allowed.

    Args:
        filename: Name of the file to check.

    Returns:
        bool: True if the file extension is allowed, False otherwise.

    Raises:
        HTTPException: If the filename is invalid or missing.
    """
    if not filename:
        logger.warning("Filename is missing or empty")
        raise HTTPException(status_code=400, detail="Filename is missing or empty")
    
    logger.debug("Checking file extension for: %s", filename)
    if "." not in filename:
        logger.warning("No file extension found in: %s", filename)
        return False
    
    extension = filename.rsplit(".", 1)[1].lower()
    is_allowed = extension in ALLOWED_EXTENSIONS
    logger.debug("Extension %s is %s", extension, "allowed" if is_allowed else "not allowed")
    return is_allowed


def get_file_mime(file: UploadFile) -> str:
    """
    Get the MIME type of the uploaded file.

    Args:
        file: Uploaded file to check.

    Returns:
        str: MIME type of the file.

    Raises:
        HTTPException: If MIME type cannot be determined.
    """
    logger.debug("Determining MIME type for file: %s", file.filename)
    try:
        with file.file as f:
            mime = magic.from_buffer(f.read(2048), mime=True)
            f.seek(0)  # Reset file pointer
        logger.debug("Detected MIME type: %s for file: %s", mime, file.filename)
        return mime
    except Exception as e:
        logger.error("Failed to determine MIME type for %s: %s", file.filename, str(e))
        raise HTTPException(status_code=500, detail="Failed to determine file MIME type")


def validate_file(file: UploadFile) -> None:
    """
    Validate the uploaded file's extension, MIME type, and size.

    Args:
        file: Uploaded file to validate.

    Raises:
        HTTPException: If file validation fails (invalid extension, MIME type, size, or mismatch).
    """
    logger.info("Validating file: %s", file.filename)
    
    # Check file size
    if file.size > MAX_FILE_SIZE:
        logger.warning("File too large: %s (size: %d bytes)", file.filename, file.size)
        raise HTTPException(
            status_code=413, detail=f"File size exceeds limit of {MAX_FILE_SIZE // 1024 // 1024}MB"
        )

    # Check file extension
    if not allowed_file(file.filename):
        logger.warning("Invalid file extension for: %s", file.filename)
        raise HTTPException(status_code=400, detail="Invalid file extension")

    # Check MIME type
    mime_type = get_file_mime(file)
    if mime_type not in ALLOWED_MIME_TYPES:
        logger.warning("Invalid MIME type: %s for file: %s", mime_type, file.filename)
        raise HTTPException(status_code=400, detail=f"Invalid MIME type: {mime_type}")

    # Check if extension matches MIME type
    file_extension = file.filename.rsplit(".", 1)[1].lower()
    expected_extension = ALLOWED_MIME_TYPES[mime_type]
    if file_extension not in (expected_extension, "jpeg" if expected_extension == "jpg" else expected_extension):
        logger.warning(
            "File extension %s does not match MIME type %s for file: %s",
            file_extension, mime_type, file.filename
        )
        raise HTTPException(
            status_code=400,
            detail=f"File extension ({file_extension}) does not match MIME type ({mime_type})"
        )

    logger.info("File validation successful for: %s", file.filename)