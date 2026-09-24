"""Test-only checkout. The trip's atomic confirmation ledger is authoritative.

Seats and their complete immutable booking are committed in ONE Mongo document
write, which is safe on standalone Mongo as well as a replica set. Other
collections are idempotent projections recoverable from that durable ledger.
"""
import hashlib
import hmac
import json
import os
import secrets
from datetime import timedelta

from fastapi import HTTPException
from pymongo import ReturnDocument

from core import db, uid, now

TEST_LABEL = 'TEST — no money charged'


def test_payments_enabled():
    return os.environ.get('ENABLE_TEST_PAYMENTS', '').lower() == 'true'


def make_credential(booking, passenger_id, qr_type):
    nonce = secrets.token_urlsafe(24)
    claims = {'id': nonce, 'booking_id': booking['id'], 'passenger_id': passenger_id,
        'trip_id': booking['trip_id'], 'bus_id': booking['bus_id'], 'bus_number': booking['bus']['number'],
        'route_id': booking['route_id'], 'type': qr_type, 'payment_mode': 'TEST',
        'boarding_point': booking['boarding_point'], 'dropping_point': booking['dropping_point'],
        'expires_at': booking['qr_expires_at'].isoformat()}
    message = 'gobus-journey-credential-v1:' + json.dumps(claims, sort_keys=True, separators=(',', ':'))
    signature = hmac.new(os.environ['JWT_SECRET'].encode(), message.encode(), hashlib.sha256).hexdigest()
    payload = f"GB1:{'S' if qr_type == 'SOURCE' else 'D'}:{nonce}:{signature}"
    return {'id': nonce, 'type': qr_type, 'payload': payload, 'status': 'NOT_VERIFIED', 'claims': claims}


def public_booking(booking, include_credentials=False):
    result = {k: v for k, v in booking.items() if k not in ['_id', 'pdf_storage_path', 'contact', 'user_id']}
    result['passengers'] = []
    for passenger in booking['passengers']:
        record = {k: v for k, v in passenger.items() if k not in ['source_qr', 'destination_qr']}
        if include_credentials:
            for key in ['source_qr', 'destination_qr']:
                record[key] = {k: passenger[key][k] for k in ['id', 'type', 'payload', 'status']}
        result['passengers'].append(record)
    return result


async def materialize(booking):
    # Mongo mutates insert dictionaries, so never reuse an inserted dict in a response.
    await db.bookings.update_one({'id': booking['id']}, {'$setOnInsert': dict(booking)}, upsert=True)
    await db.payments.update_one({'booking_id': booking['id']}, {'$setOnInsert': {
        'id': booking['payment_id'], 'booking_id': booking['id'], 'user_id': booking['user_id'],
        'mode': 'TEST', 'provider': 'GOBUS_TEST', 'status': 'TEST_SUCCESS',
        'amount': booking['total'], 'currency': 'INR', 'charged_amount': 0,
        'created_at': booking['created_at']}}, upsert=True)
    for passenger in booking['passengers']:
        for key in ['source_qr', 'destination_qr']:
            qr = passenger[key]
            await db.qr_credentials.update_one({'id': qr['id']}, {'$setOnInsert': {
                **qr['claims'], 'payload_hash': hashlib.sha256(qr['payload'].encode()).hexdigest(),
                'status': 'NOT_VERIFIED', 'created_at': booking['created_at']}}, upsert=True)
    await db.reservations.update_one({'id': booking['reservation_id']}, {'$set': {
        'status': 'CONFIRMED', 'payment_status': 'TEST_SUCCESS', 'booking_id': booking['id']}})
    await db.ticket_jobs.update_one({'booking_id': booking['id']}, {'$setOnInsert': {
        'id': uid(), 'booking_id': booking['id'], 'state': 'PENDING', 'pdf_status': 'PENDING',
        'email_status': 'PENDING', 'whatsapp_status': 'NOT_CONFIGURED',
        'whatsapp_detail': 'Twilio WhatsApp sender credentials have not been supplied. No message sent.',
        'created_at': now(), 'updated_at': now()}}, upsert=True)
    await db.audit_logs.update_one({'id': 'confirmed-' + booking['id']}, {'$setOnInsert': {
        'id': 'confirmed-' + booking['id'], 'actor_id': booking['user_id'],
        'actor_name': booking['contact']['name'], 'role': 'passenger',
        'action': 'TEST_BOOKING_CONFIRMED', 'entity_id': booking['id'],
        'detail': f"{booking['pnr']} · {TEST_LABEL}", 'created_at': booking['created_at']}}, upsert=True)


async def ledger_booking(reservation_id):
    trip = await db.trips.find_one({'confirmed_orders.reservation_id': reservation_id}, {
        '_id': 0, 'confirmed_orders': {'$elemMatch': {'reservation_id': reservation_id}}})
    return trip['confirmed_orders'][0] if trip else None


async def recover_confirmations(user_id=None):
    query = {'confirmed_orders.user_id': user_id} if user_id else {'confirmed_orders.0': {'$exists': True}}
    async for trip in db.trips.find(query, {'_id': 0, 'confirmed_orders': 1}):
        for booking in trip['confirmed_orders']:
            if (not user_id or booking['user_id'] == user_id) and not await db.ticket_jobs.find_one({'booking_id': booking['id']}):
                await materialize(booking)


async def confirm_test_payment(reservation_id, user):
    if not test_payments_enabled():
        raise HTTPException(403, 'Test payments are disabled')
    reservation = await db.reservations.find_one({'id': reservation_id, 'user_id': user['id']}, {'_id': 0})
    if not reservation:
        raise HTTPException(404, 'Reservation not found')
    previous = await ledger_booking(reservation_id)
    if previous:
        await materialize(previous)
        return previous
    trip = await db.trips.find_one({'id': reservation['trip_id']}, {'_id': 0})
    if not trip:
        raise HTTPException(404, 'Trip not found')
    hold = next((h for h in trip.get('holds', []) if h['id'] == reservation['hold_id']
                 and h['user_id'] == user['id'] and h['expires_at'] > now()), None)
    if not hold or not trip['published'] or trip['departure_at'] <= now():
        raise HTTPException(409, 'Your seat hold has expired or this trip is no longer bookable. Select seats again.')
    seat_ids = [p['seat_id'] for p in reservation['passengers']]
    if len(set(seat_ids)) != len(seat_ids) or set(seat_ids) != set(hold['seat_ids']):
        raise HTTPException(409, 'Passenger details do not match the held seats')
    seats = {s['id']: s for s in trip['layout']['seats']}
    for p in reservation['passengers']:
        seat = seats.get(p['seat_id'])
        if not seat or seat['status'] != 'AVAILABLE' or seat['type'] not in ['seat', 'berth']:
            raise HTTPException(409, 'A selected seat is no longer available')
        if seat['ladies'] and p['gender'] != 'Female':
            raise HTTPException(422, 'Ladies-reserved seats require a female passenger')
    if reservation['boarding_point'] not in trip['route']['boarding_points'] or reservation['dropping_point'] not in trip['route']['dropping_points']:
        raise HTTPException(409, 'The selected boarding or dropping point is no longer valid')
    base = sum(seats[s]['price'] for s in seat_ids)
    booking = {'id': uid(), 'reservation_id': reservation_id, 'trip_id': trip['id'],
        'user_id': user['id'], 'bus_id': trip['bus_id'], 'route_id': trip['route_id'], 'driver_id': trip['driver_id'],
        'pnr': 'GBT-' + secrets.token_hex(5).upper(), 'status': 'CONFIRMED', 'journey_status': 'BOOKED',
        'payment_id': uid(), 'payment_status': 'TEST_SUCCESS', 'payment_mode': 'TEST',
        'test_label': TEST_LABEL, 'charged_amount': 0, 'currency': 'INR',
        'base_fare': base, 'convenience_fee': trip['convenience_fee'], 'total': base + trip['convenience_fee'],
        'date': trip['date'], 'departure': trip['departure'], 'departure_at': trip['departure_at'], 'arrival_at': trip['arrival_at'],
        'bus': {k: trip['bus'][k] for k in ['name', 'number', 'operator', 'type', 'ac']},
        'route': {k: trip['route'][k] for k in ['source', 'destination', 'distance_km', 'duration_minutes']},
        'boarding_point': reservation['boarding_point'], 'dropping_point': reservation['dropping_point'],
        'contact': {k: user[k] for k in ['name', 'email', 'mobile']}, 'passengers': [],
        'qr_expires_at': trip['arrival_at'] + timedelta(hours=6), 'created_at': now()}
    for p in reservation['passengers']:
        passenger_id = uid()
        booking['passengers'].append({**p, 'id': passenger_id, 'seat_label': seats[p['seat_id']]['label'],
            'seat_type': seats[p['seat_id']]['type'], 'deck': seats[p['seat_id']]['deck'],
            'source_qr': make_credential(booking, passenger_id, 'SOURCE'),
            'destination_qr': make_credential(booking, passenger_id, 'DESTINATION')})
    committed = await db.trips.find_one_and_update({'id': trip['id'], 'published': True,
        'departure_at': {'$gt': now()}, 'status': {'$in': ['NOT_STARTED', 'READY', 'BOARDING']},
        'sold_seat_ids': {'$nin': seat_ids}, 'confirmed_orders.reservation_id': {'$ne': reservation_id},
        'holds': {'$elemMatch': {'id': hold['id'], 'user_id': user['id'],
            'seat_ids': {'$all': seat_ids, '$size': len(seat_ids)}, 'expires_at': {'$gt': now()}}}},
        {'$addToSet': {'sold_seat_ids': {'$each': seat_ids}}, '$pull': {'holds': {'id': hold['id']}},
         '$push': {'confirmed_orders': booking}}, projection={'_id': 0, 'id': 1}, return_document=ReturnDocument.AFTER)
    if not committed:
        winner = await ledger_booking(reservation_id)
        if winner:
            await materialize(winner)
            return winner
        raise HTTPException(409, 'The hold expired or seats became unavailable. No payment was charged.')
    await materialize(booking)
    return booking