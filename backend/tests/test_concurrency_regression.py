from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from dotenv import dotenv_values
from pymongo import MongoClient


IST = ZoneInfo("Asia/Kolkata")


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def login(api_client, base_url, identifier, password, portal):
    response = api_client.post(f"{base_url}/api/auth/login", json={
        "identifier": identifier,
        "password": password,
        "portal": portal,
    })
    return response


def skip_on_rate_limit(response, account: str):
    if response.status_code == 429:
        pytest.skip(f"Rate-limited for {account}; retry after window")


def skip_on_abuse_limit(response, scope: str):
    if response.status_code == 429:
        pytest.skip(f"Rate-limited for {scope}; retry after window")


def _mongo_db():
    values = dotenv_values("/app/backend/.env")
    mongo_url = values.get("MONGO_URL")
    db_name = values.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MongoDB config unavailable for hold-state verification")
    client = MongoClient(mongo_url)
    return client, client[db_name]


# Auth/mobile normalization regression coverage
def test_register_mobile_normalization_accepts_formats_and_rejects_alpha(api_client, base_url, state, uniq):
    formatted_mobile = "+91 (98765) 11122"
    register_ok = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Mobile Format",
        "email": f"qa.mobilefmt.{uniq}@example.com",
        "mobile": formatted_mobile,
        "password": "Pass@12345678",
    })
    skip_on_abuse_limit(register_ok, "register")
    assert register_ok.status_code == 201, register_ok.text
    created_user = register_ok.json()["user"]
    state.mark("users", created_user["id"])
    assert created_user["mobile"] == "+919876511122"

    login_ok = login(api_client, base_url, "+91 98765-11122", "Pass@12345678", "passenger")
    assert login_ok.status_code == 200, login_ok.text

    register_bad = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Alpha Mobile",
        "email": f"qa.mobilebad.{uniq}@example.com",
        "mobile": "+91-98AB5-11122",
        "password": "Pass@12345678",
    })
    skip_on_abuse_limit(register_bad, "register")
    assert register_bad.status_code == 422, register_bad.text


# Atomic hold concurrency + owner release + expired hold behavior
def test_simultaneous_overlapping_multi_seat_holds_are_atomic(api_client, base_url, state, uniq):
    admin_login = login(api_client, base_url, "admin@gobus.app", "Ao4mDRpGS88SHhDQ5KTgWm_G", "admin")
    skip_on_rate_limit(admin_login, "admin@gobus.app")
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    bus = api_client.post(f"{base_url}/api/admin/buses", headers=auth_headers(admin_token), json={
        "name": "TEST Concurrency Coach",
        "number": f"TEST-C{uniq[:5].upper()}",
        "operator": "TEST Ops",
        "type": "Seater + Sleeper",
        "ac": True,
        "amenities": ["Wi-Fi"],
        "active": True,
    })
    assert bus.status_code == 201, bus.text
    bus_data = bus.json()
    state.mark("buses", bus_data["id"])

    layout = {
        "rows": 8,
        "columns": 6,
        "decks": ["lower"],
        "seats": [
            {"id": "drv", "label": "DRV", "deck": "lower", "row": 0, "col": 4, "row_span": 1, "col_span": 1, "type": "driver", "price": 1, "status": "AVAILABLE", "ladies": False},
            {"id": "s1", "label": "C1", "deck": "lower", "row": 1, "col": 0, "row_span": 1, "col_span": 1, "type": "seat", "price": 900, "status": "AVAILABLE", "ladies": False},
            {"id": "s2", "label": "C2", "deck": "lower", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "type": "seat", "price": 900, "status": "AVAILABLE", "ladies": False},
            {"id": "s3", "label": "C3", "deck": "lower", "row": 1, "col": 2, "row_span": 1, "col_span": 1, "type": "seat", "price": 900, "status": "AVAILABLE", "ladies": False},
        ],
    }
    save_layout = api_client.put(f"{base_url}/api/admin/buses/{bus_data['id']}/layout", headers=auth_headers(admin_token), json=layout)
    assert save_layout.status_code == 200, save_layout.text

    route = api_client.post(f"{base_url}/api/admin/routes", headers=auth_headers(admin_token), json={
        "source": "TESTSRC",
        "destination": "TESTDST",
        "distance_km": 120,
        "duration_minutes": 180,
        "stops": ["TESTMID"],
        "boarding_points": ["TESTBoard"],
        "dropping_points": ["TESTDrop"],
        "active": True,
    })
    assert route.status_code == 201, route.text
    route_data = route.json()
    state.mark("routes", route_data["id"])

    driver = api_client.post(f"{base_url}/api/admin/staff", headers=auth_headers(admin_token), json={
        "name": "TEST Hold Driver",
        "email": f"qa.hold.driver.{uniq}@example.com",
        "mobile": "9123401234",
        "password": "Driver@12345678",
        "role": "driver",
        "license": "TEST-LICENSE-HOLD-1",
    })
    assert driver.status_code == 201, driver.text
    driver_data = driver.json()
    state.mark("users", driver_data["id"])

    date_value = (datetime.now(IST) + timedelta(days=2)).date().isoformat()
    trip = api_client.post(f"{base_url}/api/admin/trips", headers=auth_headers(admin_token), json={
        "bus_id": bus_data["id"],
        "route_id": route_data["id"],
        "driver_id": driver_data["id"],
        "date": date_value,
        "departure": "08:20",
        "convenience_fee": 30,
        "published": False,
    })
    assert trip.status_code == 201, trip.text
    trip_data = trip.json()
    state.mark("trips", trip_data["id"])

    publish = api_client.patch(f"{base_url}/api/admin/trips/{trip_data['id']}/publish", headers=auth_headers(admin_token), json={"published": True})
    assert publish.status_code == 200, publish.text

    p1 = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Hold P1",
        "email": f"qa.hold.p1.{uniq}@example.com",
        "mobile": "9981001122",
        "password": "Passenger@12345",
    })
    skip_on_abuse_limit(p1, "register")
    assert p1.status_code == 201, p1.text
    p1_id = p1.json()["user"]["id"]
    state.mark("users", p1_id)

    p2 = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Hold P2",
        "email": f"qa.hold.p2.{uniq}@example.com",
        "mobile": "9981001133",
        "password": "Passenger@12345",
    })
    skip_on_abuse_limit(p2, "register")
    assert p2.status_code == 201, p2.text
    p2_id = p2.json()["user"]["id"]
    state.mark("users", p2_id)

    p1_token = login(api_client, base_url, f"qa.hold.p1.{uniq}@example.com", "Passenger@12345", "passenger").json()["access_token"]
    p2_token = login(api_client, base_url, f"qa.hold.p2.{uniq}@example.com", "Passenger@12345", "passenger").json()["access_token"]

    seat_ids = ["s1", "s2"]

    def attempt_hold(token):
        import requests
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session.post(f"{base_url}/api/trips/{trip_data['id']}/holds", headers=auth_headers(token), json={"seat_ids": seat_ids})

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_1 = pool.submit(attempt_hold, p1_token)
        future_2 = pool.submit(attempt_hold, p2_token)
        r1 = future_1.result(timeout=15)
        r2 = future_2.result(timeout=15)

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409], f"expected [200,409], got {statuses}; bodies={[r1.text, r2.text]}"

    winner_response = r1 if r1.status_code == 200 else r2
    winner_token = p1_token if r1.status_code == 200 else p2_token
    loser_token = p2_token if winner_token == p1_token else p1_token
    winning_hold = winner_response.json()

    mongo_client, mongo_db = _mongo_db()
    try:
        trip_doc = mongo_db.trips.find_one({"id": trip_data["id"]})
        active_holds = [h for h in trip_doc.get("holds", []) if h["expires_at"] > datetime.now(tz=h["expires_at"].tzinfo)]
        overlapping = [h for h in active_holds if set(h.get("seat_ids", [])) & set(seat_ids)]
        assert len(overlapping) == 1
        assert set(overlapping[0]["seat_ids"]) == set(seat_ids)
    finally:
        mongo_client.close()

    conflict_after_win = api_client.post(
        f"{base_url}/api/trips/{trip_data['id']}/holds",
        headers=auth_headers(loser_token),
        json={"seat_ids": seat_ids},
    )
    assert conflict_after_win.status_code == 409, conflict_after_win.text

    release = api_client.delete(
        f"{base_url}/api/trips/{trip_data['id']}/holds/{winning_hold['id']}",
        headers=auth_headers(winner_token),
    )
    assert release.status_code == 200, release.text

    loser_can_hold_after_release = api_client.post(
        f"{base_url}/api/trips/{trip_data['id']}/holds",
        headers=auth_headers(loser_token),
        json={"seat_ids": seat_ids},
    )
    assert loser_can_hold_after_release.status_code == 200, loser_can_hold_after_release.text

    loser_hold = loser_can_hold_after_release.json()
    mongo_client, mongo_db = _mongo_db()
    try:
        mongo_db.trips.update_one(
            {"id": trip_data["id"], "holds.id": loser_hold["id"]},
            {"$set": {"holds.$.expires_at": datetime.now(IST) - timedelta(seconds=5)}},
        )
    finally:
        mongo_client.close()

    expired_reservation = api_client.post(f"{base_url}/api/reservations", headers=auth_headers(loser_token), json={
        "trip_id": trip_data["id"],
        "hold_id": loser_hold["id"],
        "passengers": [
            {"name": "TEST Rider 1", "age": 26, "gender": "Female", "seat_id": seat_ids[0]},
            {"name": "TEST Rider 2", "age": 32, "gender": "Male", "seat_id": seat_ids[1]},
        ],
        "boarding_point": "TESTBoard",
        "dropping_point": "TESTDrop",
    })
    assert expired_reservation.status_code == 409, expired_reservation.text
