import os
import uuid
from dataclasses import dataclass, field

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


def _base_url() -> str:
    url = os.environ.get("EXPO_BACKEND_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    if not url:
        values = dotenv_values("/app/frontend/.env")
        url = values.get("EXPO_BACKEND_URL") or values.get("EXPO_PUBLIC_BACKEND_URL")
    if not url:
        pytest.skip("Backend base URL not configured")
    return str(url).rstrip("/")


@pytest.fixture(scope="session")
def base_url() -> str:
    return _base_url()


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()


@dataclass
class TestState:
    ids: dict = field(default_factory=lambda: {k: [] for k in [
        "users", "buses", "routes", "trips", "offers", "support_tickets", "reservations"
    ]})
    values: dict = field(default_factory=dict)

    def mark(self, collection: str, value: str):
        if value:
            self.ids[collection].append(value)


@pytest.fixture(scope="session")
def state() -> TestState:
    return TestState()


@pytest.fixture(scope="session", autouse=True)
def cleanup_created_records(state: TestState):
    yield
    mongo_url = dotenv_values("/app/backend/.env").get("MONGO_URL")
    db_name = dotenv_values("/app/backend/.env").get("DB_NAME")
    if not mongo_url or not db_name:
        return
    client = MongoClient(mongo_url)
    db = client[db_name]
    try:
        for collection, ids in state.ids.items():
            if ids:
                db[collection].delete_many({"id": {"$in": ids}})
    finally:
        client.close()


@pytest.fixture(scope="session")
def uniq():
    return f"t1_{uuid.uuid4().hex[:8]}"
