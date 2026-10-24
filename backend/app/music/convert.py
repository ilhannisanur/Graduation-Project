from app.contracts import Track
from app.music.models import TrackRow


def track_from_row(row: TrackRow) -> Track:
    """Convert a database row to the shared Track contract (file_path is not exposed)."""
    return Track(
        id=row.id,
        title=row.title,
        artist=row.artist,
        duration_seconds=row.duration_seconds,
        license=row.license,
        license_url=row.license_url,
        source_url=row.source_url,
        mood_tags=list(row.mood_tags or []),
        valence=row.valence,
        arousal=row.arousal,
    )
