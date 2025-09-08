from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings
from contextlib import asynccontextmanager
from app.models.redis_helper import redis_helper


@asynccontextmanager
async def lifespan(app:FastAPI):
    await redis_helper.start()
    print("REDIS HELPER STARTED")
    yield
    await redis_helper.stop()
    print("REDIS HELPER STOPPED")

app = FastAPI(lifespan=lifespan)

app.include_router(api_router,prefix=settings.API_V1_STR)
    
    