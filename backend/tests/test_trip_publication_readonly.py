import pytest


# Passenger trip-search publication verification module (read-only public GET checks)
def test_public_search_2026_09_25_returns_expected_published_trip(api_client, base_url):
    response = api_client.get(
        f"{base_url}/api/trips",
        params={
            "source": "blgm",
            "destination": "bengaluru",
            "journey_date": "2026-09-25",
            "passengers": 1,
        },
    )
    assert response.status_code == 200, response.text

    trips = response.json()
    target = next((t for t in trips if t.get("id") == "b44a6dbc-1209-41a5-8751-e99804bbe51f"), None)
    assert target is not None, f"Expected trip id not found. Returned ids: {[t.get('id') for t in trips]}"
    assert target.get("published") is True
    assert target.get("bus", {}).get("number") == "KA01M2222"
    assert target.get("route", {}).get("source") == "blgm"
    assert target.get("route", {}).get("destination") == "bengaluru"
    assert target.get("departure") == "07:30"
    assert isinstance(target.get("available_seats"), int)
    assert target.get("available_seats") >= 1


# Passenger trip-search publication verification module (second date read-only check)
def test_public_search_2026_09_26_returns_expected_published_trip(api_client, base_url):
    response = api_client.get(
        f"{base_url}/api/trips",
        params={
            "source": "blgm",
            "destination": "bengaluru",
            "journey_date": "2026-09-26",
            "passengers": 1,
        },
    )
    assert response.status_code == 200, response.text

    trips = response.json()
    target = next((t for t in trips if t.get("id") == "fd33d2b8-bf02-4eec-9094-9bd4c279797f"), None)
    assert target is not None, f"Expected trip id not found. Returned ids: {[t.get('id') for t in trips]}"
    assert target.get("published") is True
    assert target.get("bus", {}).get("number") == "KA01M2222"
    assert target.get("route", {}).get("source") == "blgm"
    assert target.get("route", {}).get("destination") == "bengaluru"
    assert target.get("departure") == "07:30"
    assert isinstance(target.get("available_seats"), int)
    assert target.get("available_seats") >= 1


# Reverse-direction guard module (ensure target trip ids are not leaked to opposite route search)
@pytest.mark.parametrize("journey_date", ["2026-09-25", "2026-09-26"])
def test_reverse_search_does_not_return_target_trip_ids(api_client, base_url, journey_date):
    response = api_client.get(
        f"{base_url}/api/trips",
        params={
            "source": "bengaluru",
            "destination": "blgm",
            "journey_date": journey_date,
            "passengers": 1,
        },
    )
    assert response.status_code == 200, response.text
    ids = {t.get("id") for t in response.json()}
    assert "b44a6dbc-1209-41a5-8751-e99804bbe51f" not in ids
    assert "fd33d2b8-bf02-4eec-9094-9bd4c279797f" not in ids
