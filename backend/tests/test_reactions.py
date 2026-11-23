import pytest
from fastapi.testclient import TestClient

from app.api import reactions
from app.main import app


@pytest.fixture(autouse=True)
def empty_store():
    reactions.reset()
    yield
    reactions.reset()


def test_reaction_is_listed_after_the_given_id():
    client = TestClient(app)

    sent = client.post("/api/station/reactions", json={"emoji": "❤️"})
    listed = client.get("/api/station/reactions", params={"after": 0}).json()

    assert sent.status_code == 201
    assert [r["emoji"] for r in listed["items"]] == ["❤️"]
    assert listed["latest"] == sent.json()["id"]
    assert "🔥" in listed["emoji"]
    newer = client.get("/api/station/reactions", params={"after": listed["latest"]}).json()
    assert newer["items"] == []


def test_unknown_emoji_is_refused():
    response = TestClient(app).post("/api/station/reactions", json={"emoji": "💩"})
    assert response.status_code == 422


def test_one_client_cannot_flood_the_screen():
    for _ in range(reactions.PER_CLIENT):
        reactions.add_reaction("👏", "phone-1", now=100.0)

    with pytest.raises(OverflowError):
        reactions.add_reaction("👏", "phone-1", now=100.5)
    reactions.add_reaction("👏", "phone-2", now=100.5)  # another phone is fine
    reactions.add_reaction("👏", "phone-1", now=100.0 + reactions.WINDOW_S + 0.1)  # later again


def test_only_the_last_reactions_are_kept():
    for i in range(reactions.KEEP + 10):
        reactions.add_reaction("🔥", f"phone-{i}")

    listed = reactions.reactions_after(0)

    assert len(listed.items) == reactions.KEEP
    assert listed.items[0].id == 11
