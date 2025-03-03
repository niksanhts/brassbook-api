import logging

import uvicorn
from fastapi import FastAPI

from app.routes import router

logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
