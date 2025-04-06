import logging

import magic
from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "mp3", "wav"}
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
}


def allowed_file(filename: str) -> bool:
    logging.debug(f"Checking if file extension is allowed: {filename}")
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_mime(file: UploadFile) -> str:
    logging.debug(f"Getting MIME type for file: {file.filename}")
    mime = magic.from_buffer(file.file.read(2048), mime=True)
    file.file.seek(0)  # Возвращаем указатель файла в начало
    return mime


def validate_file(file: UploadFile):
    # Проверка расширения
    if not allowed_file(file.filename):
        logging.warning(f"Invalid file extension: {file.filename}")
        raise HTTPException(status_code=400, detail="Недопустимое расширение файла.")

    # Проверка MIME-типа
    mime_type = get_file_mime(file)
    if mime_type not in ALLOWED_MIME_TYPES:
        logging.warning(f"Invalid MIME type: {mime_type}")
        raise HTTPException(status_code=400, detail="Недопустимый MIME-тип файла.")

    # Проверка соответствия расширения и MIME-типа
    file_extension = file.filename.rsplit(".", 1)[1].lower()
    expected_extension = ALLOWED_MIME_TYPES[mime_type]

    if file_extension != expected_extension:
        logging.warning(
            f"File extension ({file_extension}) does not match MIME type ({mime_type})"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Расширение файла ({file_extension}) не соответствует MIME-типу ({mime_type}).",
        )
    logging.info(f"File validation successful: {file.filename}")
