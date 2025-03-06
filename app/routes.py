import logging
import asyncio

from fastapi import APIRouter, File, UploadFile

from .core.compare_melodies import compare_melodies

router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s')    

@router.post("/compare_melodies/")
async def compare_melodies_endpoint(
    file1: UploadFile = File(...), file2: UploadFile = File(...)
):
    logging.info("Начало сравнения мелодий")
    try:
        file1_content = await file1.read()
        file2_content = await file2.read()

        result = await asyncio.to_thread(
            compare_melodies,
            file1_content,
            file2_content 
        )

        if result is None:
            return {"error": "Ошибка при сравнении мелодий"}

        return {"result": result}

    except Exception as e:
        logging.error("Ошибка в функции %s: %s", __name__, str(e))
        return {"error": str(e)}