import json

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.contracts import (
    AnnouncementSegment,
    AnnouncementSpec,
    BulletinSegment,
    Emotion,
    ListenerContext,
    RequestIntent,
    Segment,
    SongRequest,
    Track,
    TrackSegment,
)

TRACK = {
    "id": "trk_001",
    "title": "Morning Rain",
    "artist": "Some Artist",
    "duration_seconds": 184.5,
    "license": "CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "source_url": "https://example.org/tracks/morning-rain",
    "mood_tags": ["calm", "acoustic"],
    "valence": 0.62,
    "arousal": 0.25,
}

ANNOUNCEMENT_SPEC = {
    "kind": "song_intro",
    "text": "Here is a gentle one to start your morning.",
    "emotion": "calm",
    "target_seconds": 8.0,
    "language": "en",
}

TRACK_SEGMENT = {
    "type": "track",
    "id": "seg_001",
    "duration_seconds": 184.5,
    "track_id": "trk_001",
    "selection_reason": "Matches your calm morning mood.",
    "request_id": "req_001",
}

ANNOUNCEMENT_SEGMENT = {
    "type": "announcement",
    "id": "seg_002",
    "duration_seconds": 8.0,
    "spec": ANNOUNCEMENT_SPEC,
    "audio_url": "/audio/seg_002.mp3",
}

BULLETIN_SEGMENT = {
    "type": "bulletin",
    "id": "seg_003",
    "duration_seconds": 45.0,
    "items": [
        {
            "title": "City opens new bike lanes",
            "summary": "Ten kilometers of lanes opened downtown today.",
            "source_name": "Example News",
            "source_url": "https://example.org/news/bike-lanes",
            "published_at": "2025-01-15T08:30:00Z",
        }
    ],
}

LISTENER_CONTEXT = {
    "local_time": "2025-01-15T09:00:00+03:00",
    "city": "Istanbul",
    "weather_summary": "Light rain, 8°C",
    "preferred_genres": ["jazz", "ambient"],
    "news_topics": ["technology", "science"],
}

REQUEST_INTENT = {
    "song_title": "Morning Rain",
    "artist": None,
    "mood": "calm",
    "message": "For my sister's birthday",
}

SONG_REQUEST = {
    "id": "req_001",
    "session_id": "ses_001",
    "raw_text": "Play Morning Rain for my sister's birthday",
    "intent": REQUEST_INTENT,
    "status": "accepted",
    "reject_reason": None,
    "estimated_play_time": "2025-01-15T09:10:00+03:00",
}

MODEL_EXAMPLES = [
    (Track, TRACK),
    (AnnouncementSpec, ANNOUNCEMENT_SPEC),
    (TrackSegment, TRACK_SEGMENT),
    (AnnouncementSegment, ANNOUNCEMENT_SEGMENT),
    (BulletinSegment, BULLETIN_SEGMENT),
    (ListenerContext, LISTENER_CONTEXT),
    (RequestIntent, REQUEST_INTENT),
    (SongRequest, SONG_REQUEST),
]


@pytest.mark.parametrize(("model", "example"), MODEL_EXAMPLES)
def test_round_trip(model: type[BaseModel], example: dict):
    obj = model.model_validate(example)
    again = model.model_validate_json(obj.model_dump_json())
    assert again == obj


@pytest.mark.parametrize(
    ("example", "expected"),
    [
        (TRACK_SEGMENT, TrackSegment),
        (ANNOUNCEMENT_SEGMENT, AnnouncementSegment),
        (BULLETIN_SEGMENT, BulletinSegment),
    ],
)
def test_segment_union_picks_by_type(example: dict, expected: type):
    adapter = TypeAdapter(Segment)
    seg = adapter.validate_python(example)
    assert isinstance(seg, expected)
    assert adapter.validate_json(adapter.dump_json(seg)) == seg


def test_segment_unknown_type_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(Segment).validate_python({**TRACK_SEGMENT, "type": "jingle"})


def test_segment_requires_id():
    data = {k: v for k, v in TRACK_SEGMENT.items() if k != "id"}
    with pytest.raises(ValidationError):
        TrackSegment.model_validate(data)


def test_segment_optional_fields_default_to_none():
    seg = TrackSegment(id="seg_9", track_id="trk_001")
    assert seg.duration_seconds is None
    assert seg.request_id is None


def test_enums_serialize_as_lowercase_text():
    spec = AnnouncementSpec.model_validate(ANNOUNCEMENT_SPEC)
    data = json.loads(spec.model_dump_json())
    assert data["emotion"] == "calm"
    assert data["kind"] == "song_intro"
    assert json.loads(SongRequest.model_validate(SONG_REQUEST).model_dump_json())["status"] == (
        "accepted"
    )
    assert json.loads(TypeAdapter(Emotion).dump_json(Emotion.HAPPY)) == "happy"


def test_unknown_emotion_rejected():
    with pytest.raises(ValidationError):
        AnnouncementSpec.model_validate({**ANNOUNCEMENT_SPEC, "emotion": "furious"})


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_valence_out_of_range_rejected(value: float):
    with pytest.raises(ValidationError):
        Track.model_validate({**TRACK, "valence": value})


@pytest.mark.parametrize("value", [-5, 0, 2.9, 120.1])
def test_target_seconds_out_of_range_rejected(value: float):
    with pytest.raises(ValidationError):
        AnnouncementSpec.model_validate({**ANNOUNCEMENT_SPEC, "target_seconds": value})


@pytest.mark.parametrize("value", [3, 120])
def test_target_seconds_bounds_accepted(value: float):
    AnnouncementSpec.model_validate({**ANNOUNCEMENT_SPEC, "target_seconds": value})


def test_listener_context_rejects_extra_field():
    with pytest.raises(ValidationError):
        ListenerContext.model_validate({**LISTENER_CONTEXT, "email": "a@b.com"})


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        ListenerContext.model_validate({**LISTENER_CONTEXT, "local_time": "2025-01-15T09:00:00"})


def test_empty_bulletin_rejected():
    with pytest.raises(ValidationError):
        BulletinSegment.model_validate({**BULLETIN_SEGMENT, "items": []})
