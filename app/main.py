import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.routes.auth_routes import auth_router
from app.api.routes.compare_routes import compare_router
from app.api.routes.user_routes import avatar_user_router, current_user_router
from app.api.routes.legacy_router import router as legacy_router


import logging

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
    )

app = FastAPI(root_path="/api")
#app.include_router(auth_router) # TODO: добработкть эти контроллеры
#app.include_router(current_user_router)
#app.include_router(avatar_user_router)

app.include_router(compare_router)
app.include_router(legacy_router)
app.include_router(avatar_user_router)
app.include_router(current_user_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
