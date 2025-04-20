import asyncio
import logging
from authx import RequestToken
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import ValidationError
from app.core.auth import security

from app.api.file_validation import validate_file
from app.core.compare_melodies import compare_melodies
from app.config import MAX_FILE_SIZE

logger = logging.getLogger(__name__)

compare_router = APIRouter(prefix="/v2/compare", tags=["compare"])


@compare_router.post("/melodies/file",
                    summary="Compare two audio files for melody similarity",
                    dependencies=[Depends(security.get_token_from_request)])
async def compare_melodies(
    file1: UploadFile = File(...), file2: UploadFile = File(...), token: RequestToken = Depends()
):
    """
    Compare two uploaded audio files to determine melody similarity.

    Args:
        file1: First audio file to compare.
        file2: Second audio file to compare.

    Returns:
        dict: Comparison result or error message.

    Raises:
        HTTPException: If file validation fails, file is too large, or comparison fails.
    """
    

    logger.info("Received request to compare melodies: %s, %s", file1.filename, file2.filename)
    
    try:

        security.verify_token(token=token)
        
        # Validate file size
        if file1.size > MAX_FILE_SIZE or file2.size > MAX_FILE_SIZE:
            logger.warning("File too large: %s or %s", file1.filename, file2.filename)
            raise HTTPException(
                status_code=413, detail="File size exceeds limit of 10MB"
            )

        # Validate file types and content
        logger.debug("Validating files: %s, %s", file1.filename, file2.filename)
        validate_file(file1)
        validate_file(file2)

        # Read file contents
        async with file1 as f1, file2 as f2:
            file1_content = await f1.read()
            file2_content = await f2.read()

        # Compare melodies in a separate thread to avoid blocking
        logger.debug("Starting melody comparison")
        result = await asyncio.to_thread(compare_melodies, file1_content, file2_content)

        if result is None:
            logger.error("Melody comparison returned None")
            raise HTTPException(
                status_code=500, detail="Error during melody comparison"
            )

        logger.info("Melody comparison completed successfully")
        return {"result": result}

    except ValidationError as ve:
        logger.error("File validation failed: %s", str(ve))
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(ve)}")
    except RuntimeError as re:
        logger.error("Melody comparison failed: %s", str(re))
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(re)}")
    except Exception as e:
        logger.error("Unexpected error during melody comparison: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")