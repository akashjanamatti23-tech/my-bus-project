from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from typing import Literal

from core import db, now, audit, Input, Record
from auth import driver_user

router = APIRouter(prefix='/driver', dependencies=[Depends(driver_user)])
TRANSITIONS = {'NOT_STARTED': 'READY', 'READY': 'BOARDING', 'BOARDING': 'JOURNEY_STARTED',
               'JOURNEY_STARTED': 'IN_TRANSIT', 'IN_TRANSIT': 'ARRIVED', 'ARRIVED': 'COMPLETED'}


class Status(Input):
    status: Literal['READY', 'BOARDING', 'JOURNEY_STARTED', 'IN_TRANSIT', 'ARRIVED', 'COMPLETED']


async def assigned(trip_id, user):
    trip = await db.trips.find_one({'id': trip_id, 'driver_id': user['id'], 'published': True}, {'_id': 0})
    if not trip:
        raise HTTPException(404, 'This trip is not assigned to you')
    return trip


def operational(trip):
    layout = {**trip['layout'], 'seats': [{k: v for k, v in s.items() if k != 'price'} for s in trip['layout']['seats']]}
    return {k: trip[k] for k in ['id', 'date', 'departure', 'departure_at', 'arrival_at', 'status', 'route', 'sold_seat_ids']} | {
        'bus': {k: trip['bus'][k] for k in ['id', 'name', 'number', 'type', 'ac']}, 'layout': layout}


@router.get('/trips', response_model=list[Record])
async def my_trips(user=Depends(driver_user)):
    values = await db.trips.find({'driver_id': user['id'], 'published': True}, {'_id': 0}).sort('departure_at', 1).to_list(500)
    return [operational(t) for t in values]


@router.get('/trips/{trip_id}', response_model=Record)
async def trip(trip_id: str, user=Depends(driver_user)):
    return operational(await assigned(trip_id, user))


@router.get('/trips/{trip_id}/passengers')
async def passengers(trip_id: str, user=Depends(driver_user)):
    await assigned(trip_id, user)
    return await db.bookings.find({'trip_id': trip_id, 'status': {'$ne': 'CANCELLED'}},
        {'_id': 0, 'id': 1, 'pnr': 1, 'passengers.name': 1, 'passengers.seat_id': 1,
         'boarding_point': 1, 'dropping_point': 1, 'journey_status': 1}).to_list(500)


@router.post('/trips/{trip_id}/status', response_model=Record)
async def set_status(trip_id: str, body: Status, user=Depends(driver_user)):
    trip = await assigned(trip_id, user)
    if trip['date'] > now().astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat():
        raise HTTPException(409, 'Trip controls open on the scheduled journey date')
    if TRANSITIONS.get(trip['status']) != body.status:
        raise HTTPException(409, 'Invalid trip transition. Follow the journey steps in order.')
    # Passenger verification must be implemented before any paid trip can advance.
    if trip.get('sold_seat_ids') and body.status in ['JOURNEY_STARTED', 'COMPLETED']:
        raise HTTPException(409, 'Passenger checkpoint verification is required before this transition')
    result = await db.trips.update_one({'id': trip_id, 'driver_id': user['id'], 'status': trip['status']},
        {'$set': {'status': body.status, 'updated_at': now()}, '$push': {'status_history': {'status': body.status, 'at': now()}}})
    if not result.modified_count:
        raise HTTPException(409, 'Trip status changed. Please refresh.')
    await audit(user, 'TRIP_' + body.status, trip_id)
    return operational(await assigned(trip_id, user))