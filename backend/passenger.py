from datetime import timedelta, date
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument

from core import db, uid, now, get_record, Record
from auth import passenger_user, current_user
from models import Hold, Reservation, Support

router = APIRouter()


def safe_trip(trip, user_id=None):
    hidden = {'_id', 'holds', 'driver_id', 'driver_name', 'created_at'}
    value = {k: v for k, v in trip.items() if k not in hidden}
    locked = {seat for h in trip.get('holds', []) if h['expires_at'] > now() and h['user_id'] != user_id for seat in h['seat_ids']}
    value['seat_states'] = {s['id']: ('SOLD' if s['id'] in trip.get('sold_seat_ids', []) else
        'LOCKED' if s['id'] in locked else s['status']) for s in trip['layout']['seats']}
    value['available_seats'] = sum(s['type'] in ['seat', 'berth'] and value['seat_states'][s['id']] == 'AVAILABLE' for s in trip['layout']['seats'])
    prices = [s['price'] for s in trip['layout']['seats'] if s['type'] in ['seat', 'berth'] and s['status'] != 'INACTIVE']
    value['from_price'] = min(prices) if prices else 0
    return value


@router.get('/config')
async def config():
    return {'currency': 'INR', 'timezone': 'Asia/Kolkata', 'payment_enabled': False,
        'payment_provider': 'Razorpay', 'sms_enabled': False, 'checkout_message':
        'Payments are not available yet. Your seats cannot be purchased until Razorpay is configured.'}


@router.get('/routes', response_model=list[Record])
async def routes():
    return await db.routes.find({'active': True}, {'_id': 0}).to_list(500)


@router.get('/trips', response_model=list[Record])
async def search(source: str = '', destination: str = '', journey_date: date | None = None,
                 passengers: int = Query(default=1, ge=1, le=6), ac: bool | None = None,
                 bus_type: str | None = None, sort: str = 'departure'):
    query = {'published': True, 'departure_at': {'$gt': now()}, 'status': {'$in': ['NOT_STARTED', 'READY', 'BOARDING']}}
    if journey_date:
        query['date'] = journey_date.isoformat()
    if source:
        query['route.source'] = source
    if destination:
        query['route.destination'] = destination
    if ac is not None:
        query['bus.ac'] = ac
    if bus_type:
        query['bus.type'] = bus_type
    trips = [safe_trip(t) for t in await db.trips.find(query, {'_id': 0}).limit(500).to_list(500)]
    trips = [t for t in trips if t['available_seats'] >= passengers]
    key = {'price': 'from_price', 'departure': 'departure_at', 'arrival': 'arrival_at', 'availability': 'available_seats'}.get(sort, 'departure_at')
    return sorted(trips, key=lambda t: t[key], reverse=sort == 'availability')


@router.get('/trips/{trip_id}', response_model=Record)
async def trip_detail(trip_id: str):
    trip = await get_record('trips', trip_id)
    if not trip['published']:
        raise HTTPException(404, 'This trip is not available')
    return safe_trip(trip)


@router.post('/trips/{trip_id}/holds')
async def hold_seats(trip_id: str, body: Hold, user=Depends(passenger_user)):
    seat_ids = body.seat_ids
    if len(set(seat_ids)) != len(seat_ids):
        raise HTTPException(422, 'Select each seat only once')
    trip = await get_record('trips', trip_id)
    allowed = {s['id'] for s in trip['layout']['seats'] if s['type'] in ['seat', 'berth'] and s['status'] == 'AVAILABLE'}
    if not set(seat_ids).issubset(allowed):
        raise HTTPException(422, 'One or more selected seats are unavailable')
    existing = next((h for h in trip.get('holds', []) if h['user_id'] == user['id'] and h['expires_at'] > now()), None)
    if existing:
        if set(existing['seat_ids']) == set(seat_ids):
            return existing
        raise HTTPException(409, 'Release your existing seat hold before choosing different seats')
    hold = {'id': uid(), 'user_id': user['id'], 'seat_ids': seat_ids, 'expires_at': now() + timedelta(minutes=5)}
    # A single document predicate/update atomically locks the complete requested set.
    result = await db.trips.find_one_and_update({'id': trip_id, 'published': True, 'departure_at': {'$gt': now()},
        'status': {'$in': ['NOT_STARTED', 'READY', 'BOARDING']}, 'sold_seat_ids': {'$nin': seat_ids},
        'holds': {'$not': {'$elemMatch': {'expires_at': {'$gt': now()},
            '$or': [{'seat_ids': {'$in': seat_ids}}, {'user_id': user['id']}]}}}},
        {'$push': {'holds': hold}}, projection={'_id': 0, 'id': 1}, return_document=ReturnDocument.AFTER)
    if not result:
        raise HTTPException(409, 'These seats were just selected by another passenger, or this trip is no longer bookable. Please refresh.')
    return hold


@router.delete('/trips/{trip_id}/holds/{hold_id}')
async def release_hold(trip_id: str, hold_id: str, user=Depends(passenger_user)):
    await db.trips.update_one({'id': trip_id}, {'$pull': {'holds': {'id': hold_id, 'user_id': user['id']}}})
    return {'success': True}


@router.post('/reservations', response_model=Record, status_code=201)
async def reservation(body: Reservation, user=Depends(passenger_user)):
    trip = await get_record('trips', body.trip_id)
    hold = next((h for h in trip['holds'] if h['id'] == body.hold_id and h['user_id'] == user['id'] and h['expires_at'] > now()), None)
    if not hold or not trip['published'] or trip['departure_at'] <= now():
        raise HTTPException(409, 'Your seat hold has expired. Please select your seats again.')
    selected = [p.seat_id for p in body.passengers]
    if len(set(selected)) != len(selected) or set(selected) != set(hold['seat_ids']):
        raise HTTPException(422, 'Provide one passenger for each selected seat')
    if body.boarding_point not in trip['route']['boarding_points'] or body.dropping_point not in trip['route']['dropping_points']:
        raise HTTPException(422, 'Choose a configured boarding and dropping point')
    seats = {s['id']: s for s in trip['layout']['seats']}
    for passenger in body.passengers:
        if seats[passenger.seat_id]['ladies'] and passenger.gender != 'Female':
            raise HTTPException(422, 'Ladies-reserved seats require a female passenger')
    base = sum(seats[s]['price'] for s in selected)
    values = {**body.model_dump(), 'user_id': user['id'], 'status': 'DRAFT', 'payment_status': 'NOT_INITIATED',
        'base_fare': base, 'convenience_fee': trip['convenience_fee'], 'total': base + trip['convenience_fee'],
        'expires_at': hold['expires_at'], 'updated_at': now()}
    record = await db.reservations.find_one_and_update({'user_id': user['id'], 'hold_id': hold['id']},
        {'$set': values, '$setOnInsert': {'id': uid(), 'created_at': now()}}, upsert=True,
        projection={'_id': 0}, return_document=ReturnDocument.AFTER)
    return record


@router.get('/bookings', response_model=list[Record])
async def bookings(user=Depends(passenger_user)):
    return await db.bookings.find({'user_id': user['id']}, {'_id': 0}).to_list(500)


@router.get('/offers', response_model=list[Record])
async def offers():
    return await db.offers.find({'active': True, 'valid_until': {'$gte': now().astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()}}, {'_id': 0}).to_list(100)


@router.post('/support', response_model=Record, status_code=201)
async def create_support(body: Support, user=Depends(current_user)):
    record = {'id': uid(), **body.model_dump(), 'user_id': user['id'], 'name': user['name'],
        'status': 'OPEN', 'reply': '', 'created_at': now()}
    await db.support_tickets.insert_one(dict(record))
    return record


@router.get('/support', response_model=list[Record])
async def my_support(user=Depends(current_user)):
    return await db.support_tickets.find({'user_id': user['id']}, {'_id': 0}).sort('created_at', -1).to_list(100)