from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from core import db, uid, now, audit, get_record, Record
from auth import admin_user, create_user, public_user
from models import Bus, Layout, Route, Staff, Trip, Toggle, Publish, Offer, SupportReply

router = APIRouter(prefix='/admin', dependencies=[Depends(admin_user)])
IST = ZoneInfo('Asia/Kolkata')


@asynccontextmanager
async def configuration_lock():
    token = uid()
    try:
        await db.mutex.update_one({'_id': 'configuration', 'expires_at': {'$lt': now()}},
            {'$set': {'token': token, 'expires_at': now() + timedelta(seconds=30)}}, upsert=True)
    except DuplicateKeyError:
        raise HTTPException(409, 'Another configuration change is in progress. Please try again.')
    try:
        yield
    finally:
        await db.mutex.delete_one({'_id': 'configuration', 'token': token})


async def assert_unused(field, identifier):
    if await db.trips.find_one({field: identifier, 'published': True, 'arrival_at': {'$gt': now()}}):
        raise HTTPException(409, 'Unpublish upcoming trips before changing their bus, route or driver configuration')


@router.get('/dashboard')
async def dashboard():
    buses = await db.buses.count_documents({})
    trips = await db.trips.find({}, {'_id': 0, 'holds': 0}).to_list(10000)
    bookings = await db.bookings.find({}, {'_id': 0}).to_list(10000)
    today = now().astimezone(IST).date().isoformat()
    return {'total_buses': buses, 'active_buses': await db.buses.count_documents({'active': True}),
        'routes': await db.routes.count_documents({}), 'drivers': await db.users.count_documents({'role': 'driver', 'active': True}),
        'total_bookings': len(bookings), 'revenue': sum(b.get('total', 0) for b in bookings if b.get('payment_status') == 'SUCCESS'),
        'published_trips': sum(t['published'] for t in trips),
        'active_journeys': sum(t['status'] in ['JOURNEY_STARTED', 'IN_TRANSIT'] for t in trips),
        'todays_trips': sum(t['date'] == today for t in trips),
        'support_tickets': await db.support_tickets.count_documents({'status': {'$ne': 'RESOLVED'}}),
        'recent_activity': await db.audit_logs.find({}, {'_id': 0}).sort('created_at', -1).limit(6).to_list(6)}


@router.get('/buses', response_model=list[Record])
async def buses():
    return await db.buses.find({}, {'_id': 0}).sort('created_at', -1).to_list(500)


@router.post('/buses', response_model=Record, status_code=201)
async def create_bus(body: Bus, user=Depends(admin_user)):
    bus = {'id': uid(), **body.model_dump(), 'layout': None, 'created_at': now()}
    try:
        await db.buses.insert_one(dict(bus))
    except DuplicateKeyError:
        raise HTTPException(409, 'This bus registration number is already in use')
    await audit(user, 'BUS_CREATED', bus['id'], bus['number'])
    return bus


@router.put('/buses/{bus_id}', response_model=Record)
async def update_bus(bus_id: str, body: Bus, user=Depends(admin_user)):
    async with configuration_lock():
        await get_record('buses', bus_id)
        await assert_unused('bus_id', bus_id)
        try:
            await db.buses.update_one({'id': bus_id}, {'$set': body.model_dump()})
        except DuplicateKeyError:
            raise HTTPException(409, 'This bus registration number is already in use')
        await audit(user, 'BUS_UPDATED', bus_id)
    return await get_record('buses', bus_id)


@router.put('/buses/{bus_id}/layout', response_model=Record)
async def save_layout(bus_id: str, body: Layout, user=Depends(admin_user)):
    async with configuration_lock():
        await get_record('buses', bus_id)
        await assert_unused('bus_id', bus_id)
        await db.buses.update_one({'id': bus_id}, {'$set': {'layout': body.model_dump(), 'updated_at': now()}})
        await audit(user, 'LAYOUT_SAVED', bus_id, f'{len(body.seats)} configured elements')
    return await get_record('buses', bus_id)


@router.get('/routes', response_model=list[Record])
async def routes():
    return await db.routes.find({}, {'_id': 0}).sort('created_at', -1).to_list(500)


@router.post('/routes', response_model=Record, status_code=201)
async def create_route(body: Route, user=Depends(admin_user)):
    route = {'id': uid(), **body.model_dump(), 'created_at': now()}
    await db.routes.insert_one(dict(route))
    await audit(user, 'ROUTE_CREATED', route['id'], f"{route['source']} → {route['destination']}")
    return route


@router.put('/routes/{route_id}', response_model=Record)
async def update_route(route_id: str, body: Route, user=Depends(admin_user)):
    async with configuration_lock():
        await get_record('routes', route_id)
        await assert_unused('route_id', route_id)
        await db.routes.update_one({'id': route_id}, {'$set': body.model_dump()})
        await audit(user, 'ROUTE_UPDATED', route_id)
    return await get_record('routes', route_id)


@router.get('/staff', response_model=list[Record])
async def staff():
    return await db.users.find({'role': {'$in': ['admin', 'driver']}}, {'_id': 0, 'password_hash': 0}).to_list(500)


@router.post('/staff', response_model=Record, status_code=201)
async def create_staff(body: Staff, user=Depends(admin_user)):
    if body.role == 'admin' and user['role'] != 'super_admin':
        raise HTTPException(403, 'Only Super Admin can create Admin accounts')
    if body.role == 'driver' and not body.license.strip():
        raise HTTPException(422, 'A driving license number is required')
    person = await create_user(body, body.role)
    await audit(user, 'STAFF_CREATED', person['id'], person['role'])
    return public_user(person)


@router.patch('/staff/{person_id}', response_model=Record)
async def toggle_staff(person_id: str, body: Toggle, user=Depends(admin_user)):
    async with configuration_lock():
        person = await get_record('users', person_id)
        if person['role'] not in ['admin', 'driver'] or (person['role'] == 'admin' and user['role'] != 'super_admin'):
            raise HTTPException(403, 'This account cannot be changed by your role')
        await assert_unused('driver_id', person_id)
        await db.users.update_one({'id': person_id}, {'$set': {'active': body.active}})
        if not body.active:
            await db.sessions.update_many({'user_id': person_id}, {'$set': {'revoked': True}})
        await audit(user, 'STAFF_STATUS_CHANGED', person_id)
    return public_user(await get_record('users', person_id))


async def trip_resources(body):
    bus = await get_record('buses', body.bus_id)
    route = await get_record('routes', body.route_id)
    driver = await get_record('users', body.driver_id)
    if not bus['active'] or not route['active'] or not driver['active'] or driver['role'] != 'driver':
        raise HTTPException(422, 'Choose an active bus, route and driver')
    layout = bus.get('layout')
    if not layout or not any(s['type'] in ['seat', 'berth'] and s['status'] == 'AVAILABLE' for s in layout['seats']):
        raise HTTPException(422, 'Configure available seats in the bus layout before scheduling')
    if not any(s['type'] == 'driver' for s in layout['seats']):
        raise HTTPException(422, 'Place the driver cabin in the bus layout before scheduling')
    return bus, route, driver


@router.get('/trips', response_model=list[Record])
async def trips():
    return await db.trips.find({}, {'_id': 0, 'holds': 0}).sort('departure_at', -1).to_list(500)


@router.post('/trips', response_model=Record, status_code=201)
async def create_trip(body: Trip, user=Depends(admin_user)):
    async with configuration_lock():
        bus, route, driver = await trip_resources(body)
        departure = datetime.fromisoformat(f'{body.date.isoformat()}T{body.departure}').replace(tzinfo=IST)
        arrival = departure + timedelta(minutes=route['duration_minutes'])
        if departure <= now():
            raise HTTPException(422, 'Departure must be in the future (India Standard Time)')
        if await db.trips.find_one({'$or': [{'bus_id': bus['id']}, {'driver_id': driver['id']}],
            'departure_at': {'$lt': arrival}, 'arrival_at': {'$gt': departure}, 'published': True}):
            raise HTTPException(409, 'This bus or driver is already assigned during these hours')
        trip = {'id': uid(), **body.model_dump(mode='json'), 'departure_at': departure, 'arrival_at': arrival,
            'bus': bus, 'route': route, 'driver_name': driver['name'], 'layout': bus['layout'],
            'status': 'NOT_STARTED', 'holds': [], 'sold_seat_ids': [], 'created_at': now()}
        await db.trips.insert_one(dict(trip))
        await audit(user, 'TRIP_CREATED', trip['id'], f"{route['source']} → {route['destination']}")
    return {k: v for k, v in trip.items() if k != 'holds'}


@router.patch('/trips/{trip_id}/publish', response_model=Record)
async def publish(trip_id: str, body: Publish, user=Depends(admin_user)):
    async with configuration_lock():
        trip = await get_record('trips', trip_id)
        if trip['status'] != 'NOT_STARTED' or trip['departure_at'] <= now():
            raise HTTPException(409, 'Only future, unstarted trips can be changed')
        if trip.get('sold_seat_ids'):
            raise HTTPException(409, 'A trip with sold seats cannot be unpublished')
        values = {'published': body.published}
        if body.published:
            bus, route, driver = await trip_resources(Trip(**{k: trip[k] for k in Trip.model_fields}))
            arrival = trip['departure_at'] + timedelta(minutes=route['duration_minutes'])
            if await db.trips.find_one({'id': {'$ne': trip_id}, 'published': True,
                '$or': [{'bus_id': trip['bus_id']}, {'driver_id': trip['driver_id']}],
                'departure_at': {'$lt': arrival}, 'arrival_at': {'$gt': trip['departure_at']}}):
                raise HTTPException(409, 'Bus or driver has an overlapping published trip')
            values.update(bus=bus, route=route, layout=bus['layout'], driver_name=driver['name'], arrival_at=arrival)
        result = await db.trips.update_one({'id': trip_id,
            'holds': {'$not': {'$elemMatch': {'expires_at': {'$gt': now()}}}}}, {'$set': values})
        if not result.matched_count:
            raise HTTPException(409, 'Seats are temporarily held. Try again when the holds expire.')
        await audit(user, 'TRIP_PUBLISHED' if body.published else 'TRIP_UNPUBLISHED', trip_id)
    result = await get_record('trips', trip_id)
    result.pop('holds', None)
    return result


@router.get('/offers', response_model=list[Record])
async def offers():
    return await db.offers.find({}, {'_id': 0}).to_list(500)


@router.post('/offers', response_model=Record, status_code=201)
async def create_offer(body: Offer, user=Depends(admin_user)):
    offer = {'id': uid(), **body.model_dump(mode='json'), 'created_at': now()}
    await db.offers.insert_one(dict(offer))
    await audit(user, 'OFFER_CREATED', offer['id'], offer['code'])
    return offer


@router.put('/offers/{offer_id}', response_model=Record)
async def update_offer(offer_id: str, body: Offer, user=Depends(admin_user)):
    await get_record('offers', offer_id)
    await db.offers.update_one({'id': offer_id}, {'$set': body.model_dump(mode='json')})
    await audit(user, 'OFFER_UPDATED', offer_id)
    return await get_record('offers', offer_id)


@router.get('/audit', response_model=list[Record])
async def audit_history(user=Depends(admin_user)):
    query = {} if user['role'] == 'super_admin' else {'role': {'$ne': 'super_admin'}}
    return await db.audit_logs.find(query, {'_id': 0}).sort('created_at', -1).limit(200).to_list(200)


@router.get('/support', response_model=list[Record])
async def support():
    return await db.support_tickets.find({}, {'_id': 0}).sort('created_at', -1).to_list(500)


@router.patch('/support/{ticket_id}', response_model=Record)
async def support_reply(ticket_id: str, body: SupportReply, user=Depends(admin_user)):
    await get_record('support_tickets', ticket_id)
    await db.support_tickets.update_one({'id': ticket_id}, {'$set': {'reply': body.reply, 'status': body.status, 'updated_at': now()}})
    await audit(user, 'SUPPORT_REPLIED', ticket_id)
    return await get_record('support_tickets', ticket_id)