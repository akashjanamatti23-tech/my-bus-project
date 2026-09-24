import os
from functools import lru_cache
import requests
from fastapi import APIRouter, HTTPException, Response
from starlette.concurrency import run_in_threadpool
from core import db

router = APIRouter()
BASE = (os.environ.get('INTEGRATION_PROXY_URL') or '').strip() or 'https://integrations.emergentagent.com'
STORAGE_URL = BASE.rstrip('/') + '/objstore/api/v1/storage'


@lru_cache(maxsize=1)
def storage_key():
    result = requests.post(STORAGE_URL + '/init', json={'emergent_key': os.environ.get('EMERGENT_LLM_KEY')}, timeout=30)
    result.raise_for_status()
    return result.json()['storage_key']


def upload(path, data):
    result = requests.put(f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': storage_key(),
        'Content-Type': 'image/jpeg'}, data=data, timeout=120)
    result.raise_for_status()
    return result.json()


@lru_cache(maxsize=4)
def download(path):
    result = requests.get(f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': storage_key()}, timeout=30)
    if result.status_code == 503:
        storage_key.cache_clear()
        result = requests.get(f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': storage_key()}, timeout=30)
    result.raise_for_status()
    return result.content


@router.get('/media/hero')
async def hero():
    # Only this explicitly public brand asset is exposed; arbitrary storage paths are not accepted.
    asset = await db.assets.find_one({'name': 'passenger-hero', 'public': True}, {'_id': 0})
    if not asset:
        raise HTTPException(404, 'Brand image not configured')
    try:
        data = await run_in_threadpool(download, asset['storage_path'])
    except requests.RequestException:
        raise HTTPException(503, 'Image temporarily unavailable')
    return Response(data, media_type='image/jpeg', headers={'Cache-Control': 'public, max-age=86400'})