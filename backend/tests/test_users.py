import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.auth import COOKIE_NAME
from app.db.session import get_db
from app.main import app
from app.users import AuthSessionRow, UserProfileRow, UserRow
from app.users.context import listener_context
from app.users.schemas import Profile, RegisterRequest, normalize_username
from app.users.security import hash_password, token_hash, verify_password

PASSWORD = "correct horse battery"

# --------------------------------------------------------------------- no database


def test_password_hash_verifies_and_is_not_the_password():
    hashed = hash_password(PASSWORD)

    assert hashed.startswith("$argon2id$")
    assert PASSWORD not in hashed
    assert verify_password(hashed, PASSWORD)
    assert not verify_password(hashed, "wrong password")
    assert not verify_password("not-a-hash", PASSWORD)


def test_username_is_lowercased_and_checked():
    assert RegisterRequest(username="  Nisa_01 ", password=PASSWORD).username == "nisa_01"
    for bad in ["ab", "x" * 33, "has space", "ümlaut", "a/b"]:
        with pytest.raises(ValidationError):
            RegisterRequest(username=bad, password=PASSWORD)


def test_bad_username_error_names_the_field_and_the_rule():
    response = TestClient(app).post(
        "/api/auth/register", json={"username": "has space", "password": PASSWORD}
    )

    assert response.status_code == 422
    issue = response.json()["detail"][0]
    assert issue["loc"] == ["body", "username"]
    assert "no spaces" in issue["msg"]


@pytest.mark.parametrize("typed", ["NİSA", "Nİsa", "NISA", "nısa", " nisa "])
def test_turkish_keyboard_spellings_mean_the_same_username(typed):
    # On a Turkish keyboard the capital of 'i' is 'İ'; Python alone would lowercase it to
    # 'i' + a combining dot and miss the account.
    assert normalize_username(typed) == "nisa"
    assert RegisterRequest(username=typed, password=PASSWORD).username == "nisa"


def test_password_length_limits():
    with pytest.raises(ValidationError):
        RegisterRequest(username="nisa", password="short")
    with pytest.raises(ValidationError):
        RegisterRequest(username="nisa", password="x" * 129)


def test_profile_accepts_only_known_choices():
    with pytest.raises(ValidationError):
        Profile(genres=["pop", "not-a-genre"])
    with pytest.raises(ValidationError):
        Profile(languages=["klingon"])
    with pytest.raises(ValidationError):
        Profile(news_topics=["gossip"])


def test_profile_cleans_its_input():
    profile = Profile(
        genres=["jazz", "jazz", "pop"],
        artists=[" Some Band ", "some band", "Other"],
        weather_city="   ",
    )

    assert profile.genres == ["jazz", "pop"]
    assert profile.artists == ["Some Band", "Other"]
    assert profile.weather_city is None


@pytest.mark.parametrize(
    ("typed", "kept"),
    [
        (["Çağan Şengül", "ÇAĞAN ŞENGÜL"], ["Çağan Şengül"]),
        (["Barış Manço", "BARIŞ MANÇO"], ["Barış Manço"]),
        (["İlhan İrem", "ilhan irem"], ["İlhan İrem"]),
        (["Sezen  Aksu", "Sezen Aksu"], ["Sezen Aksu"]),
        (["Kevin MacLeod", "KEVIN MACLEOD"], ["Kevin MacLeod"]),
        # NFD (decomposed, as some keyboards send it) and NFC forms of the same name
        (["Şebnem Ferah", "Şebnem Ferah"], ["Şebnem Ferah"]),
    ],
)
def test_artist_duplicates_are_found_in_turkish_too(typed, kept):
    assert Profile(artists=typed).artists == kept


def test_listener_context_carries_no_identity():
    profile = UserProfileRow(
        user_id="usr_secret123",
        genres=["jazz"],
        artists=["My Friend's Band"],
        languages=["en"],
        news_topics=["science"],
        weather_city="Ankara",
    )
    now = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)

    context = listener_context(profile, now, weather_summary="Sunny, 15°C")
    sent = context.model_dump_json()

    assert context.city == "Ankara"
    assert context.preferred_genres == ["jazz"]
    assert context.news_topics == ["science"]
    assert "usr_secret123" not in sent
    assert "My Friend's Band" not in sent


# ------------------------------------------------------------------------ database


@pytest.fixture
def client(db_session: Session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def unique_name() -> str:
    # The tests share the developer's database, where real accounts (e.g. "nisa") may exist.
    return f"test_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def name() -> str:
    return unique_name()


def register(client: TestClient, username: str, password: str = PASSWORD):
    return client.post("/api/auth/register", json={"username": username, "password": password})


def test_register_logs_in_with_a_safe_cookie(client: TestClient, name: str):
    response = register(client, name)

    assert response.status_code == 201
    assert response.json()["username"] == name
    cookie = response.headers["set-cookie"]
    assert f"{COOKIE_NAME}=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api" in cookie
    assert client.get("/api/me").json()["username"] == name


def test_password_and_token_are_never_stored_or_returned_in_plain(
    client: TestClient, db_session: Session, name: str
):
    response = register(client, name)
    token = client.cookies[COOKIE_NAME]

    user = db_session.scalar(select(UserRow).where(UserRow.username == name))
    stored = db_session.scalars(
        select(AuthSessionRow.token_hash).where(AuthSessionRow.user_id == user.id)
    ).all()
    assert PASSWORD not in user.password_hash
    assert PASSWORD not in response.text
    assert stored == [token_hash(token)]
    assert token not in stored


def test_username_is_unique_ignoring_case(client: TestClient, name: str):
    register(client, name)

    response = register(client, name.upper())

    assert response.status_code == 409


def test_new_account_has_an_empty_profile(client: TestClient, name: str):
    register(client, name)

    assert client.get("/api/me/profile").json() == {
        "genres": [],
        "artists": [],
        "languages": [],
        "news_topics": [],
        "weather_city": None,
    }


def test_login_and_wrong_login(client: TestClient, name: str):
    register(client, name)
    client.cookies.clear()

    assert client.get("/api/me").status_code == 401
    ok = client.post("/api/auth/login", json={"username": name.upper(), "password": PASSWORD})
    assert ok.status_code == 200
    assert client.get("/api/me").status_code == 200

    wrong_password = client.post("/api/auth/login", json={"username": name, "password": "nope"})
    no_user = client.post("/api/auth/login", json={"username": unique_name(), "password": "nope"})
    assert wrong_password.status_code == no_user.status_code == 401
    # Same answer either way: it does not reveal which usernames exist.
    assert wrong_password.json() == no_user.json()


def test_login_with_turkish_capital_i(client: TestClient):
    name = f"nisa_{uuid.uuid4().hex[:8]}"
    register(client, name)
    client.cookies.clear()

    turkish_upper = name.replace("i", "İ").upper()  # what a Turkish keyboard types: NİSA_...
    response = client.post(
        "/api/auth/login", json={"username": turkish_upper, "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["username"] == name


def test_logout_ends_the_session_on_the_server(client: TestClient, name: str):
    register(client, name)
    token = client.cookies[COOKIE_NAME]

    assert client.post("/api/auth/logout").status_code == 204

    # Even a copy of the old cookie no longer works.
    client.cookies.set(COOKIE_NAME, token, path="/api")
    assert client.get("/api/me").status_code == 401


def test_expired_session_is_rejected(client: TestClient, db_session: Session, name: str):
    register(client, name)
    db_session.execute(
        update(AuthSessionRow)
        .where(AuthSessionRow.token_hash == token_hash(client.cookies[COOKIE_NAME]))
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db_session.flush()

    assert client.get("/api/me").status_code == 401


def test_made_up_cookie_is_rejected(client: TestClient):
    client.cookies.set(COOKIE_NAME, "made-up-token", path="/api")

    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me/profile").status_code == 401


def test_profile_can_be_saved_and_changed(client: TestClient, name: str):
    register(client, name)
    profile = {
        "genres": ["jazz", "ambient"],
        "artists": ["Some Band"],
        "languages": ["en", "tr"],
        "news_topics": ["science"],
        "weather_city": "Ankara",
    }

    assert client.put("/api/me/profile", json=profile).json() == profile
    assert client.get("/api/me/profile").json() == profile

    changed = {**profile, "genres": ["rock"], "weather_city": None}
    assert client.put("/api/me/profile", json=changed).status_code == 200
    assert client.get("/api/me/profile").json() == changed


def test_profile_rejects_unknown_choices(client: TestClient, name: str):
    register(client, name)

    response = client.put("/api/me/profile", json={"genres": ["not-a-genre"]})

    assert response.status_code == 422


def test_profiles_are_private_to_their_owner(client: TestClient):
    register(client, unique_name())
    client.put("/api/me/profile", json={"weather_city": "Ankara"})
    client.cookies.clear()
    register(client, unique_name())

    assert client.get("/api/me/profile").json()["weather_city"] is None


def test_profile_options_are_public():
    response = TestClient(app).get("/api/profile/options")

    assert response.status_code == 200
    values = [option["value"] for option in response.json()["genres"]]
    assert "jazz" in values
