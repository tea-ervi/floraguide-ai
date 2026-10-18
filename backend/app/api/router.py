from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.endpoints import categories, plants, user_plants

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(categories.router)
api_router.include_router(plants.router)
api_router.include_router(user_plants.router)
