from fastapi import UploadFile, File
import shutil

async def save_profile_picture(file: UploadFile):
    file_location = f"images/{file.filename}"  # Путь, куда будет сохранено изображение
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_location