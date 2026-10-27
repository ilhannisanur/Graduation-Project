import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import COOKIE_NAME
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.radio.planner import current_planner
from app.users import ConsentRow, UserRow, service
from app.users.privacy import CONSENT_KINDS, PREFERENCE_LEARNING

PASSWORD = "correct horse battery"


def tables_with_user_data():
    """(table, column) for every column that points at users.id."""
    found = []
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name == "users" and fk.column.name == "id":
                found.append((table, fk.parent))
    return found


# --------------------------------------------------------------------- no database


def test_every_table_with_user_data_is_deleted_with_the_account():
    # A new table that stores user data but forgets ON DELETE CASCADE fails here.
    found = tables_with_user_data()

    assert {t.name for t, _ in found} >= {"auth_sessions", "user_profiles", "user_consents"}
    for table, column in found:
        (fk,) = column.foreign_keys
        assert fk.ondelete == "CASCADE", f"{table.name}.{column.name} must cascade"


def test_privacy_notice_is_public_and_versioned():
    response = TestClient(app).get("/api/privacy")

    assert response.status_code == 200
    body = response.json()
    assert body["version"]
    assert set(body["consents"]) == set(CONSENT_KINDS)
    titles = [s["title"] for s in body["sections"]]
    assert "What the AI presenter sees" in titles


# ------------------------------------------------------------------------ database


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client: TestClient, **extra) -> dict:
    name = f"test_{uuid.uuid4().hex[:12]}"
    response = client.post(
        "/api/auth/register", json={"username": name, "password": PASSWORD, **extra}
    )
    assert response.status_code == 201
    return response.json()


def consent_rows(db: Session, user_id: str) -> int:
    return db.scalar(select(func.count()).where(ConsentRow.user_id == user_id))


def test_learning_is_off_unless_chosen_and_the_choice_is_recorded(
    client: TestClient, db_session: Session
):
    user = register(client)

    state = client.get("/api/me/consents").json()[PREFERENCE_LEARNING]
    assert state["granted"] is False
    assert state["notice_version"]  # the decision was offered and recorded
    assert not service.may_learn_preferences(db_session, user["id"])


def test_learning_can_be_chosen_at_sign_up(client: TestClient, db_session: Session):
    user = register(client, preference_learning=True)

    assert client.get("/api/me/consents").json()[PREFERENCE_LEARNING]["granted"] is True
    assert service.may_learn_preferences(db_session, user["id"])


def test_learning_can_be_turned_on_and_off_with_history(client: TestClient, db_session: Session):
    user = register(client)

    on = client.put("/api/me/consents", json={"preference_learning": True})
    assert on.json()[PREFERENCE_LEARNING]["granted"] is True
    client.put("/api/me/consents", json={"preference_learning": True})  # no change
    off = client.put("/api/me/consents", json={"preference_learning": False})

    assert off.json()[PREFERENCE_LEARNING]["granted"] is False
    assert not service.may_learn_preferences(db_session, user["id"])
    assert consent_rows(db_session, user["id"]) == 3  # sign-up, on, off (not the repeat)


def test_consents_need_a_login(client: TestClient):
    assert client.get("/api/me/consents").status_code == 401
    assert client.put("/api/me/consents", json={"preference_learning": True}).status_code == 401


def test_download_contains_my_data_and_no_secrets(client: TestClient, db_session: Session):
    user = register(client, preference_learning=True)
    client.put("/api/me/profile", json={"genres": ["jazz"], "weather_city": "Ankara"})
    token = client.cookies[COOKIE_NAME]

    response = client.get("/api/me/data")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    data = response.json()
    assert data["account"]["username"] == user["username"]
    assert data["profile"]["genres"] == ["jazz"]
    assert data["profile"]["weather_city"] == "Ankara"
    assert data["consents"][0]["kind"] == PREFERENCE_LEARNING
    assert len(data["sign_ins"]) == 1
    password_hash = db_session.get(UserRow, user["id"]).password_hash
    for secret in [PASSWORD, password_hash, token, service.token_hash(token)]:
        assert secret not in response.text


def test_download_has_only_my_data(client: TestClient):
    register(client)
    client.put("/api/me/profile", json={"weather_city": "Ankara"})
    client.cookies.clear()
    other = register(client)

    data = client.get("/api/me/data").json()

    assert data["account"]["id"] == other["id"]
    assert "Ankara" not in str(data)


def test_delete_needs_the_password(client: TestClient):
    register(client)

    response = client.request("DELETE", "/api/me", json={"password": "not my password"})

    assert response.status_code == 403
    assert client.get("/api/me").status_code == 200  # still there


def test_delete_removes_every_trace(client: TestClient, db_session: Session):
    user = register(client, preference_learning=True)
    client.put("/api/me/profile", json={"genres": ["jazz"], "artists": ["Some Band"]})
    client.post("/api/auth/login", json={"username": user["username"], "password": PASSWORD})

    response = client.request("DELETE", "/api/me", json={"password": PASSWORD})

    assert response.status_code == 204
    assert f'{COOKIE_NAME}=""' in response.headers["set-cookie"]  # cookie cleared
    assert db_session.get(UserRow, user["id"]) is None
    for table, column in tables_with_user_data():
        left = db_session.scalar(
            select(func.count()).select_from(table).where(column == user["id"])
        )
        assert left == 0, f"{table.name} still has rows of the deleted user"
    # Signing in no longer works, and the name is free again.
    login = client.post(
        "/api/auth/login", json={"username": user["username"], "password": PASSWORD}
    )
    assert login.status_code == 401
    again = client.post(
        "/api/auth/register", json={"username": user["username"], "password": PASSWORD}
    )
    assert again.status_code == 201


def test_delete_closes_listening_sessions(client: TestClient):
    class FakePlanner:
        def __init__(self) -> None:
            self.closed_for: list[str] = []

        def close_user_sessions(self, user_id: str) -> int:
            self.closed_for.append(user_id)
            return 1

    planner = FakePlanner()
    app.dependency_overrides[current_planner] = lambda: planner
    user = register(client)

    client.request("DELETE", "/api/me", json={"password": PASSWORD})

    assert planner.closed_for == [user["id"]]
