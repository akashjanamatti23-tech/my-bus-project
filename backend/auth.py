import hashlib
import os
import re
import time
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool

from core import db, now, uid, audit, Record
from models import Register, Login

router = APIRouter(prefix='/auth')
hasher = PasswordHash.recommended()
DUMMY_HASH = hasher.hash('not-a-real-user-password')
bearer = HTTPBearer(auto_error=False)
SECRET = os.environ['JWT_SECRET']


async def rate_limit(key, limit=12, window=900):
    digest = hashlib.sha256(key.encode()).hexdigest()
    bucket = f'{digest}:{int(time.time()) // window}'
    record = await db.rate_limits.find_one_and_update({'_id': bucket},
        {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': now() + timedelta(seconds=window * 2)}},
        upsert=True, return_document=ReturnDocument.AFTER)
    if record['count'] > limit:
        raise HTTPException(429, 'Too many attempts. Please try again later.', headers={'Retry-After': str(window)})


def public_user(user):
    return {k: user[k] for k in ['id', 'name', 'email', 'mobile', 'role', 'active', 'mobile_verified', 'driver_code', 'license'] if k in user}


async def create_user(data, role):
    values = data.model_dump(exclude={'password', 'role'})
    user = {**values, 'id': uid(), 'role': role, 'active': True, 'mobile_verified': False,
        'password_hash': await run_in_threadpool(hasher.hash, data.password), 'created_at': now()}
    if role == 'driver':
        user['driver_code'] = 'GB-' + uid()[:8].upper()
    try:
        await db.users.insert_one(dict(user))
    except DuplicateKeyError:
        raise HTTPException(409, 'An account with this email or mobile already exists')
    return user


async def session(user):
    jti, expiry = uid(), now() + timedelta(minutes=60)
    token = jwt.encode({'sub': user['id'], 'jti': jti, 'iat': now(), 'exp': expiry,
        'iss': 'gobus', 'aud': 'gobus-app'}, SECRET, algorithm='HS256')
    await db.sessions.insert_one({'jti': jti, 'user_id': user['id'], 'expires_at': expiry, 'revoked': False})
    return {'access_token': token, 'expires_at': expiry, 'user': public_user(user)}


async def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, 'Please sign in to continue')
    try:
        claims = jwt.decode(credentials.credentials, SECRET, algorithms=['HS256'], audience='gobus-app', issuer='gobus',
                            options={'require': ['sub', 'jti', 'exp']})
    except jwt.PyJWTError:
        raise HTTPException(401, 'Your session expired. Please sign in again.')
    valid = await db.sessions.find_one({'jti': claims['jti'], 'user_id': claims['sub'],
        'revoked': False, 'expires_at': {'$gt': now()}}, {'_id': 0})
    user = await db.users.find_one({'id': claims['sub'], 'active': True}, {'_id': 0, 'password_hash': 0})
    if not valid or not user:
        raise HTTPException(401, 'Session no longer active')
    user['_session'] = claims['jti']
    return user


def require(*roles):
    async def dependency(user=Depends(current_user)):
        if user['role'] not in roles:
            raise HTTPException(403, 'You do not have permission for this operation')
        return user
    return dependency


admin_user = require('admin', 'super_admin')
passenger_user = require('passenger')
driver_user = require('driver')


@router.post('/register', status_code=201)
async def register(body: Register, request: Request):
    await rate_limit('register:' + request.client.host, 20, 3600)
    user = await create_user(body, 'passenger')
    await audit(user, 'ACCOUNT_CREATED', user['id'])
    return await session(user)


@router.post('/login')
async def login(body: Login, request: Request):
    identifier = body.identifier.strip().lower()
    if '@' not in identifier and not identifier.startswith('gb-'):
        digits = re.sub(r'\D', '', identifier)
        identifier = '+91' + digits if len(digits) == 10 else '+' + digits
    await rate_limit('login-account:' + identifier, 15, 900)
    await rate_limit('login-ip:' + request.client.host, 80, 900)
    user = await db.users.find_one({'$or': [{'email': identifier}, {'mobile': identifier},
        {'driver_code': identifier.upper()}]}, {'_id': 0})
    valid = await run_in_threadpool(hasher.verify, body.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid or not user['active']:
        raise HTTPException(401, 'Email, mobile or password is incorrect')
    allowed = {'admin': ['admin', 'super_admin'], 'driver': ['driver'], 'passenger': ['passenger']}
    if user['role'] not in allowed[body.portal]:
        raise HTTPException(403, 'This account belongs to a different GoBus interface')
    await audit(user, 'SIGN_IN', user['id'])
    return await session(user)


@router.get('/me', response_model=Record)
async def me(user=Depends(current_user)):
    return public_user(user)


@router.post('/logout')
async def logout(user=Depends(current_user)):
    await db.sessions.update_one({'jti': user['_session']}, {'$set': {'revoked': True}})
    return {'success': True}