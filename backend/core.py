import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict

load_dotenv(Path(__file__).parent / '.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'], tz_aware=True)
db = client[os.environ['DB_NAME']]


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid.uuid4())


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Record(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str


async def get_record(collection, record_id):
    result = await db[collection].find_one({'id': record_id}, {'_id': 0})
    if not result:
        raise HTTPException(404, 'Record not found')
    return result


async def audit(user, action, entity_id, detail=''):
    await db.audit_logs.insert_one({'id': uid(), 'actor_id': user['id'],
        'actor_name': user['name'], 'role': user['role'], 'action': action,
        'entity_id': entity_id, 'detail': detail, 'created_at': now()})


async def indexes():
    for collection in ['users', 'buses', 'routes', 'trips', 'offers', 'support_tickets', 'reservations', 'bookings', 'payments', 'qr_credentials', 'ticket_jobs']:
        await db[collection].create_index('id', unique=True)
    for key in ['email', 'mobile', 'driver_code']:
        await db.users.create_index(key, unique=True, sparse=True)
    await db.sessions.create_index('jti', unique=True)
    await db.sessions.create_index('expires_at', expireAfterSeconds=0)
    await db.rate_limits.create_index('expires_at', expireAfterSeconds=0)
    await db.trips.create_index([('date', 1), ('published', 1)])
    await db.buses.create_index('number', unique=True)
    await db.bookings.create_index('reservation_id', unique=True, sparse=True)
    await db.bookings.create_index([('user_id', 1), ('created_at', -1)])
    await db.payments.create_index('booking_id', unique=True)
    await db.ticket_jobs.create_index('booking_id', unique=True)
    await db.ticket_links.create_index('token_hash', unique=True)
    await db.ticket_links.create_index('expires_at', expireAfterSeconds=0)
    await db.trips.create_index('confirmed_orders.user_id')