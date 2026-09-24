import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware
from core import db, client, indexes
from auth import router as auth_router
from admin import router as admin_router
from passenger import router as passenger_router
from driver import router as driver_router
from media import router as media_router


@asynccontextmanager
async def lifespan(app):
    await db.command('ping')
    await indexes()
    yield
    client.close()


app = FastAPI(title='GoBus Central Platform', lifespan=lifespan)
api = APIRouter(prefix='/api')


@api.get('/health')
async def health():
    await db.command('ping')
    return {'status': 'ok', 'app': 'GoBus', 'stage': 'foundation', 'payment_enabled': False}


for router in [auth_router, admin_router, passenger_router, driver_router, media_router]:
    api.include_router(router)
app.include_router(api)
app.add_middleware(CORSMiddleware,
    allow_origins=[s.strip() for s in os.environ.get('CORS_ORIGINS', '').split(',') if s.strip()],
    allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type'])