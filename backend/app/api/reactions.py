"""Listener reactions: emoji sent from phones, floating over the studio screen.

    POST /api/station/reactions               {"emoji": "❤️"}  (no login: it is anonymous)
    GET  /api/station/reactions?after=<id>    reactions newer than id

Nothing is stored in the database: the last reactions live in memory for a short time, which is
all the screen needs. Only a fixed set of emoji is accepted, and each client (IP address) may
send a few per second, so a phone cannot flood the screen.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/station/reactions", tags=["station"])

EMOJI = ("❤️", "😂", "😮", "😢", "🔥", "👏")
KEEP = 200  # reactions kept in memory
PER_CLIENT = 5  # at most this many ...
WINDOW_S = 3.0  # ... per this many seconds, per client


class ReactionIn(BaseModel):
    emoji: str


class Reaction(BaseModel):
    id: int
    emoji: str


class Reactions(BaseModel):
    emoji: list[str]  # the accepted set, for the phone page
    latest: int  # newest id; the screen starts from here
    items: list[Reaction]


@dataclass
class _Store:
    items: deque
    next_id: int
    recent: dict[str, deque]
    lock: threading.Lock


_store = _Store(items=deque(maxlen=KEEP), next_id=1, recent={}, lock=threading.Lock())


def add_reaction(emoji: str, client: str, now: float | None = None) -> Reaction:
    """Store a reaction. Raises ValueError for an unknown emoji, OverflowError when too fast."""
    if emoji not in EMOJI:
        raise ValueError(emoji)
    now = time.monotonic() if now is None else now
    with _store.lock:
        sent = _store.recent.setdefault(client, deque())
        while sent and now - sent[0] > WINDOW_S:
            sent.popleft()
        if len(sent) >= PER_CLIENT:
            raise OverflowError(client)
        sent.append(now)
        reaction = Reaction(id=_store.next_id, emoji=emoji)
        _store.next_id += 1
        _store.items.append(reaction)
        if len(_store.recent) > 1000:  # forget idle clients
            for key in [k for k, v in _store.recent.items() if not v]:
                del _store.recent[key]
        return reaction


def reactions_after(after: int) -> Reactions:
    with _store.lock:
        items = [r for r in _store.items if r.id > after]
        latest = _store.next_id - 1
    return Reactions(emoji=list(EMOJI), latest=latest, items=items)


def reset() -> None:
    """Empty the store (tests)."""
    with _store.lock:
        _store.items.clear()
        _store.recent.clear()
        _store.next_id = 1


@router.post("", status_code=201)
def react(body: ReactionIn, request: Request) -> Reaction:
    client = request.client.host if request.client else "unknown"
    try:
        return add_reaction(body.emoji, client)
    except ValueError:
        raise HTTPException(status_code=422, detail="Unknown emoji") from None
    except OverflowError:
        raise HTTPException(status_code=429, detail="Slow down a little") from None


@router.get("")
def list_reactions(after: int = Query(0, ge=0)) -> Reactions:
    return reactions_after(after)
