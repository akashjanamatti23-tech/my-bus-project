from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest


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


# Auth + RBAC module coverage
def test_auth_registration_portal_logout_and_disable_flow(api_client, base_url, state, uniq):
    passenger_mobile_digits = "9876501234"
    passenger_password = "Pass@12345678"
    passenger_email = f"qa.passenger.{uniq}@example.com"

    register_response = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Passenger One",
        "email": passenger_email,
        "mobile": passenger_mobile_digits,
        "password": passenger_password,
    })
    skip_on_abuse_limit(register_response, "register")
    assert register_response.status_code == 201, register_response.text
    register_data = register_response.json()
    state.mark("users", register_data["user"]["id"])

    assert register_data["user"]["mobile"] == "+919876501234"
    assert "password_hash" not in register_data["user"]

    dup_response = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Passenger Duplicate",
        "email": f"qa.dup.{uniq}@example.com",
        "mobile": "+919876501234",
        "password": passenger_password,
    })
    skip_on_abuse_limit(dup_response, "register")
    assert dup_response.status_code == 409, dup_response.text

    escalation_response = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Bad Role",
        "email": f"qa.badrole.{uniq}@example.com",
        "mobile": "9988776655",
        "password": passenger_password,
        "role": "admin",
    })
    skip_on_abuse_limit(escalation_response, "register")
    assert escalation_response.status_code == 422, escalation_response.text

    wrong_portal = login(api_client, base_url, passenger_email, passenger_password, "admin")
    assert wrong_portal.status_code == 403, wrong_portal.text

    passenger_login = login(api_client, base_url, passenger_email, passenger_password, "passenger")
    assert passenger_login.status_code == 200, passenger_login.text
    passenger_token = passenger_login.json()["access_token"]

    me_ok = api_client.get(f"{base_url}/api/auth/me", headers=auth_headers(passenger_token))
    assert me_ok.status_code == 200, me_ok.text

    logout = api_client.post(f"{base_url}/api/auth/logout", headers=auth_headers(passenger_token))
    assert logout.status_code == 200, logout.text

    me_after_logout = api_client.get(f"{base_url}/api/auth/me", headers=auth_headers(passenger_token))
    assert me_after_logout.status_code == 401, me_after_logout.text

    admin_login = login(api_client, base_url, "admin@gobus.app", "Ao4mDRpGS88SHhDQ5KTgWm_G", "admin")
    skip_on_rate_limit(admin_login, "admin@gobus.app")
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    driver_email = f"qa.driver.{uniq}@example.com"
    driver_mobile = "9123456701"
    driver_password = "Driver@12345678"

    create_driver = api_client.post(f"{base_url}/api/admin/staff", headers=auth_headers(admin_token), json={
        "name": "TEST Driver One",
        "email": driver_email,
        "mobile": driver_mobile,
        "password": driver_password,
        "role": "driver",
        "license": "TEST-LICENSE-001",
    })
    assert create_driver.status_code == 201, create_driver.text
    driver = create_driver.json()
    state.mark("users", driver["id"])

    disable_driver = api_client.patch(
        f"{base_url}/api/admin/staff/{driver['id']}",
        headers=auth_headers(admin_token),
        json={"active": False},
    )
    assert disable_driver.status_code == 200, disable_driver.text

    disabled_login = login(api_client, base_url, driver_email, driver_password, "driver")
    assert disabled_login.status_code == 401, disabled_login.text


# Admin + Layout + Scheduling module coverage
def test_admin_layout_schedule_publish_search_and_guards(api_client, base_url, state, uniq):
    admin_login = login(api_client, base_url, "admin@gobus.app", "Ao4mDRpGS88SHhDQ5KTgWm_G", "admin")
    skip_on_rate_limit(admin_login, "admin@gobus.app")
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    dashboard = api_client.get(f"{base_url}/api/admin/dashboard", headers=auth_headers(admin_token))
    assert dashboard.status_code == 200, dashboard.text
    assert "total_buses" in dashboard.json()

    bus_number = f"TEST-{uniq[:4].upper()}-01"
    create_bus = api_client.post(f"{base_url}/api/admin/buses", headers=auth_headers(admin_token), json={
        "name": "TEST Intercity Coach",
        "number": bus_number,
        "operator": "TEST Operator",
        "type": "Seater + Sleeper",
        "ac": True,
        "amenities": ["Wi-Fi", "Water"],
        "active": True,
    })
    assert create_bus.status_code == 201, create_bus.text
    bus = create_bus.json()
    state.mark("buses", bus["id"])

    duplicate_bus = api_client.post(f"{base_url}/api/admin/buses", headers=auth_headers(admin_token), json={
        "name": "TEST Duplicate Coach",
        "number": bus_number,
        "operator": "TEST Operator",
        "type": "Seater",
        "ac": True,
        "amenities": [],
        "active": True,
    })
    assert duplicate_bus.status_code == 409, duplicate_bus.text

    create_route = api_client.post(f"{base_url}/api/admin/routes", headers=auth_headers(admin_token), json={
        "source": "TESTCityA",
        "destination": "TESTCityB",
        "distance_km": 320,
        "duration_minutes": 420,
        "stops": ["TESTStop1", "TESTStop2"],
        "boarding_points": ["TESTBoardA", "TESTBoardB"],
        "dropping_points": ["TESTDropA", "TESTDropB"],
        "active": True,
    })
    assert create_route.status_code == 201, create_route.text
    route = create_route.json()
    state.mark("routes", route["id"])

    driver_email = f"qa.driver2.{uniq}@example.com"
    driver_password = "Driver2@12345678"
    create_driver = api_client.post(f"{base_url}/api/admin/staff", headers=auth_headers(admin_token), json={
        "name": "TEST Driver Two",
        "email": driver_email,
        "mobile": "9123456702",
        "password": driver_password,
        "role": "driver",
        "license": "TEST-LICENSE-002",
    })
    assert create_driver.status_code == 201, create_driver.text
    driver = create_driver.json()
    state.mark("users", driver["id"])

    duplicate_labels_layout = {
        "rows": 8,
        "columns": 6,
        "decks": ["lower"],
        "seats": [
            {"id": "drv1", "label": "DRV", "deck": "lower", "row": 0, "col": 4, "row_span": 1, "col_span": 1, "type": "driver", "price": 500, "status": "AVAILABLE", "ladies": False},
            {"id": "s1", "label": "L1", "deck": "lower", "row": 1, "col": 0, "row_span": 1, "col_span": 1, "type": "seat", "price": 800, "status": "AVAILABLE", "ladies": False},
            {"id": "s2", "label": "L1", "deck": "lower", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "type": "seat", "price": 800, "status": "AVAILABLE", "ladies": False},
        ],
    }
    bad_labels = api_client.put(
        f"{base_url}/api/admin/buses/{bus['id']}/layout",
        headers=auth_headers(admin_token),
        json=duplicate_labels_layout,
    )
    assert bad_labels.status_code == 422, bad_labels.text

    overlapping_layout = {
        "rows": 8,
        "columns": 6,
        "decks": ["lower"],
        "seats": [
            {"id": "drv1", "label": "DRV", "deck": "lower", "row": 0, "col": 4, "row_span": 1, "col_span": 1, "type": "driver", "price": 500, "status": "AVAILABLE", "ladies": False},
            {"id": "s1", "label": "A1", "deck": "lower", "row": 2, "col": 1, "row_span": 1, "col_span": 2, "type": "seat", "price": 900, "status": "AVAILABLE", "ladies": False},
            {"id": "s2", "label": "A2", "deck": "lower", "row": 2, "col": 2, "row_span": 1, "col_span": 1, "type": "seat", "price": 900, "status": "AVAILABLE", "ladies": False},
        ],
    }
    overlap = api_client.put(f"{base_url}/api/admin/buses/{bus['id']}/layout", headers=auth_headers(admin_token), json=overlapping_layout)
    assert overlap.status_code == 422, overlap.text

    out_of_bounds_layout = {
        "rows": 8,
        "columns": 6,
        "decks": ["lower"],
        "seats": [
            {"id": "drv1", "label": "DRV", "deck": "lower", "row": 0, "col": 4, "row_span": 1, "col_span": 1, "type": "driver", "price": 500, "status": "AVAILABLE", "ladies": False},
            {"id": "s1", "label": "B1", "deck": "lower", "row": 10, "col": 1, "row_span": 1, "col_span": 1, "type": "seat", "price": 900, "status": "AVAILABLE", "ladies": False},
        ],
    }
    out_of_bounds = api_client.put(f"{base_url}/api/admin/buses/{bus['id']}/layout", headers=auth_headers(admin_token), json=out_of_bounds_layout)
    assert out_of_bounds.status_code == 422, out_of_bounds.text

    # Valid layout: driver at row0 col4, custom columns, berth spanning two rows, upper deck enabled, blocked and ladies seat.
    valid_layout = {
        "rows": 8,
        "columns": 6,
        "decks": ["lower", "upper"],
        "seats": [
            {"id": "drv1", "label": "DRV", "deck": "lower", "row": 0, "col": 4, "row_span": 1, "col_span": 1, "type": "driver", "price": 500, "status": "AVAILABLE", "ladies": False},
            {"id": "lw1", "label": "L1", "deck": "lower", "row": 1, "col": 0, "row_span": 1, "col_span": 1, "type": "seat", "price": 1000, "status": "AVAILABLE", "ladies": True},
            {"id": "lw2", "label": "L2", "deck": "lower", "row": 1, "col": 2, "row_span": 1, "col_span": 1, "type": "seat", "price": 950, "status": "AVAILABLE", "ladies": False},
            {"id": "lb1", "label": "LB1", "deck": "lower", "row": 2, "col": 0, "row_span": 2, "col_span": 1, "type": "berth", "price": 1200, "status": "AVAILABLE", "ladies": False},
            {"id": "blk1", "label": "L3", "deck": "lower", "row": 4, "col": 1, "row_span": 1, "col_span": 1, "type": "seat", "price": 800, "status": "BLOCKED", "ladies": False},
            {"id": "up1", "label": "U1", "deck": "upper", "row": 1, "col": 0, "row_span": 1, "col_span": 1, "type": "seat", "price": 1100, "status": "AVAILABLE", "ladies": False},
            {"id": "up2", "label": "U2", "deck": "upper", "row": 1, "col": 2, "row_span": 1, "col_span": 1, "type": "seat", "price": 1150, "status": "AVAILABLE", "ladies": False},
            {"id": "ais1", "label": "Ais", "deck": "lower", "row": 1, "col": 1, "row_span": 3, "col_span": 1, "type": "aisle", "price": 0, "status": "AVAILABLE", "ladies": False},
        ],
    }
    save_layout = api_client.put(f"{base_url}/api/admin/buses/{bus['id']}/layout", headers=auth_headers(admin_token), json=valid_layout)
    assert save_layout.status_code == 200, save_layout.text

    bad_bus_no_driver = api_client.post(f"{base_url}/api/admin/buses", headers=auth_headers(admin_token), json={
        "name": "TEST Missing Driver Bus",
        "number": f"TEST-{uniq[:4].upper()}-02",
        "operator": "TEST Operator",
        "type": "Seater",
        "ac": True,
        "amenities": [],
        "active": True,
    })
    assert bad_bus_no_driver.status_code == 201, bad_bus_no_driver.text
    bad_bus = bad_bus_no_driver.json()
    state.mark("buses", bad_bus["id"])

    layout_without_driver = {
        "rows": 6,
        "columns": 5,
        "decks": ["lower"],
        "seats": [
            {"id": "x1", "label": "X1", "deck": "lower", "row": 1, "col": 0, "row_span": 1, "col_span": 1, "type": "seat", "price": 700, "status": "AVAILABLE", "ladies": False}
        ],
    }
    save_no_driver_layout = api_client.put(
        f"{base_url}/api/admin/buses/{bad_bus['id']}/layout",
        headers=auth_headers(admin_token),
        json=layout_without_driver,
    )
    assert save_no_driver_layout.status_code == 200, save_no_driver_layout.text

    journey_date = (datetime.now(IST) + timedelta(days=2)).date().isoformat()
    departure = "09:30"
    create_trip_no_driver_cabin = api_client.post(f"{base_url}/api/admin/trips", headers=auth_headers(admin_token), json={
        "bus_id": bad_bus["id"],
        "route_id": route["id"],
        "driver_id": driver["id"],
        "date": journey_date,
        "departure": departure,
        "convenience_fee": 50,
        "published": False,
    })
    assert create_trip_no_driver_cabin.status_code == 422, create_trip_no_driver_cabin.text

    create_trip = api_client.post(f"{base_url}/api/admin/trips", headers=auth_headers(admin_token), json={
        "bus_id": bus["id"],
        "route_id": route["id"],
        "driver_id": driver["id"],
        "date": journey_date,
        "departure": departure,
        "convenience_fee": 45,
        "published": False,
    })
    assert create_trip.status_code == 201, create_trip.text
    trip = create_trip.json()
    state.mark("trips", trip["id"])

    publish = api_client.patch(
        f"{base_url}/api/admin/trips/{trip['id']}/publish",
        headers=auth_headers(admin_token),
        json={"published": True},
    )
    assert publish.status_code == 200, publish.text

    overlap_trip = api_client.post(f"{base_url}/api/admin/trips", headers=auth_headers(admin_token), json={
        "bus_id": bus["id"],
        "route_id": route["id"],
        "driver_id": driver["id"],
        "date": journey_date,
        "departure": "10:00",
        "convenience_fee": 0,
        "published": True,
    })
    assert overlap_trip.status_code == 409, overlap_trip.text

    guarded_bus_update = api_client.put(
        f"{base_url}/api/admin/buses/{bus['id']}",
        headers=auth_headers(admin_token),
        json={
            "name": "TEST Intercity Coach Updated",
            "number": bus_number,
            "operator": "TEST Operator",
            "type": "Seater + Sleeper",
            "ac": True,
            "amenities": ["Wi-Fi", "Water"],
            "active": True,
        },
    )
    assert guarded_bus_update.status_code == 409, guarded_bus_update.text

    search_unpublished = api_client.get(
        f"{base_url}/api/trips",
        params={"source": "TESTCityA", "destination": "TESTCityB", "journey_date": journey_date, "passengers": 1},
    )
    assert search_unpublished.status_code == 200, search_unpublished.text
    assert any(t["id"] == trip["id"] for t in search_unpublished.json())

    state.values["trip_id"] = trip["id"]
    state.values["trip_date"] = journey_date
    state.values["driver_email"] = driver_email
    state.values["driver_password"] = driver_password
    state.values["route_boarding"] = "TESTBoardA"
    state.values["route_dropping"] = "TESTDropA"


# Passenger hold/reservation + offers/support + driver scope module coverage
def test_passenger_concurrency_reservation_driver_and_support(api_client, base_url, state, uniq):
    trip_id = state.values.get("trip_id")
    if not trip_id:
        pytest.skip("Trip setup unavailable from previous test")

    p1_email = f"qa.p1.{uniq}@example.com"
    p2_email = f"qa.p2.{uniq}@example.com"
    p_password = "Passenger@12345"

    p1_reg = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Passenger P1",
        "email": p1_email,
        "mobile": "9980011122",
        "password": p_password,
    })
    skip_on_abuse_limit(p1_reg, "register")
    assert p1_reg.status_code == 201, p1_reg.text
    state.mark("users", p1_reg.json()["user"]["id"])

    p2_reg = api_client.post(f"{base_url}/api/auth/register", json={
        "name": "TEST Passenger P2",
        "email": p2_email,
        "mobile": "9980011133",
        "password": p_password,
    })
    skip_on_abuse_limit(p2_reg, "register")
    assert p2_reg.status_code == 201, p2_reg.text
    state.mark("users", p2_reg.json()["user"]["id"])

    p1_token = login(api_client, base_url, p1_email, p_password, "passenger").json()["access_token"]
    p2_token = login(api_client, base_url, p2_email, p_password, "passenger").json()["access_token"]

    trip_detail = api_client.get(f"{base_url}/api/trips/{trip_id}")
    assert trip_detail.status_code == 200, trip_detail.text
    trip = trip_detail.json()

    available = [s["id"] for s in trip["layout"]["seats"] if s["type"] in ["seat", "berth"] and trip["seat_states"][s["id"]] == "AVAILABLE"]
    ladies = [s["id"] for s in trip["layout"]["seats"] if s["ladies"] and s["type"] in ["seat", "berth"]]
    assert len(available) >= 2

    hold_p1 = api_client.post(
        f"{base_url}/api/trips/{trip_id}/holds",
        headers=auth_headers(p1_token),
        json={"seat_ids": available[:2]},
    )
    assert hold_p1.status_code == 200, hold_p1.text
    hold = hold_p1.json()

    state.values["hold_id"] = hold["id"]

    hold_p1_idempotent = api_client.post(
        f"{base_url}/api/trips/{trip_id}/holds",
        headers=auth_headers(p1_token),
        json={"seat_ids": [available[1], available[0]]},
    )
    assert hold_p1_idempotent.status_code == 200, hold_p1_idempotent.text
    assert hold_p1_idempotent.json()["id"] == hold["id"]

    hold_conflict = api_client.post(
        f"{base_url}/api/trips/{trip_id}/holds",
        headers=auth_headers(p2_token),
        json={"seat_ids": [available[0]]},
    )
    assert hold_conflict.status_code == 409, hold_conflict.text

    foreign_release = api_client.delete(
        f"{base_url}/api/trips/{trip_id}/holds/{hold['id']}",
        headers=auth_headers(p2_token),
    )
    assert foreign_release.status_code == 200, foreign_release.text

    # Hold should still exist for owner because release is owner-restricted.
    still_conflict = api_client.post(
        f"{base_url}/api/trips/{trip_id}/holds",
        headers=auth_headers(p2_token),
        json={"seat_ids": [available[0]]},
    )
    assert still_conflict.status_code == 409, still_conflict.text

    invalid_reservation = api_client.post(f"{base_url}/api/reservations", headers=auth_headers(p1_token), json={
        "trip_id": trip_id,
        "hold_id": hold["id"],
        "passengers": [{"name": "TEST A", "age": 28, "gender": "Male", "seat_id": available[0]}],
        "boarding_point": state.values["route_boarding"],
        "dropping_point": state.values["route_dropping"],
    })
    assert invalid_reservation.status_code == 422, invalid_reservation.text

    if ladies:
        target = ladies[0]
        if target in hold["seat_ids"]:
            ladies_validation = api_client.post(f"{base_url}/api/reservations", headers=auth_headers(p1_token), json={
                "trip_id": trip_id,
                "hold_id": hold["id"],
                "passengers": [
                    {"name": "TEST Male", "age": 30, "gender": "Male", "seat_id": hold["seat_ids"][0]},
                    {"name": "TEST Female", "age": 29, "gender": "Female", "seat_id": hold["seat_ids"][1]},
                ],
                "boarding_point": state.values["route_boarding"],
                "dropping_point": state.values["route_dropping"],
            })
            assert ladies_validation.status_code == 422, ladies_validation.text

    reservation = api_client.post(f"{base_url}/api/reservations", headers=auth_headers(p1_token), json={
        "trip_id": trip_id,
        "hold_id": hold["id"],
        "passengers": [
            {"name": "TEST Female", "age": 28, "gender": "Female", "seat_id": hold["seat_ids"][0]},
            {"name": "TEST Male", "age": 30, "gender": "Male", "seat_id": hold["seat_ids"][1]},
        ],
        "boarding_point": state.values["route_boarding"],
        "dropping_point": state.values["route_dropping"],
    })
    assert reservation.status_code == 201, reservation.text
    draft = reservation.json()
    state.mark("reservations", draft["id"])
    assert draft["status"] == "DRAFT"
    assert draft["payment_status"] == "NOT_INITIATED"

    bookings = api_client.get(f"{base_url}/api/bookings", headers=auth_headers(p1_token))
    assert bookings.status_code == 200, bookings.text
    assert bookings.json() == []

    admin_login = login(api_client, base_url, "admin@gobus.app", "Ao4mDRpGS88SHhDQ5KTgWm_G", "admin")
    skip_on_rate_limit(admin_login, "admin@gobus.app")
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    offer_code = ("TEST" + uniq[:6]).upper().replace("_", "")
    offer = api_client.post(f"{base_url}/api/admin/offers", headers=auth_headers(admin_token), json={
        "title": "TEST Festival Offer",
        "code": offer_code,
        "description": "TEST discount for API coverage",
        "discount_percent": 10,
        "minimum_amount": 200,
        "maximum_discount": 100,
        "valid_until": (datetime.now(IST) + timedelta(days=10)).date().isoformat(),
        "active": True,
    })
    assert offer.status_code == 201, offer.text
    offer_data = offer.json()
    state.mark("offers", offer_data["id"])

    offers_for_passenger = api_client.get(f"{base_url}/api/offers")
    assert offers_for_passenger.status_code == 200, offers_for_passenger.text
    assert any(o["id"] == offer_data["id"] for o in offers_for_passenger.json())

    support = api_client.post(f"{base_url}/api/support", headers=auth_headers(p1_token), json={
        "subject": "TEST support request",
        "message": "TEST message needing admin response for coverage.",
    })
    assert support.status_code == 201, support.text
    ticket = support.json()
    state.mark("support_tickets", ticket["id"])

    reply = api_client.patch(
        f"{base_url}/api/admin/support/{ticket['id']}",
        headers=auth_headers(admin_token),
        json={"reply": "TEST resolved", "status": "RESOLVED"},
    )
    assert reply.status_code == 200, reply.text

    my_support = api_client.get(f"{base_url}/api/support", headers=auth_headers(p1_token))
    assert my_support.status_code == 200, my_support.text
    updated = next(t for t in my_support.json() if t["id"] == ticket["id"])
    assert updated["status"] == "RESOLVED"

    driver_login = login(
        api_client,
        base_url,
        state.values["driver_email"],
        state.values["driver_password"],
        "driver",
    )
    assert driver_login.status_code == 200, driver_login.text
    driver_token = driver_login.json()["access_token"]

    driver_trip = api_client.get(f"{base_url}/api/driver/trips/{trip_id}", headers=auth_headers(driver_token))
    assert driver_trip.status_code == 200, driver_trip.text
    assert "price" not in str(driver_trip.json()["layout"]["seats"][0])

    # Future-date controls should be blocked.
    bad_transition = api_client.post(
        f"{base_url}/api/driver/trips/{trip_id}/status",
        headers=auth_headers(driver_token),
        json={"status": "READY"},
    )
    assert bad_transition.status_code == 409, bad_transition.text
