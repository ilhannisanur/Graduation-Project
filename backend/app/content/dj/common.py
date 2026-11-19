WORDS_PER_SECOND = 2.5
MIN_SECONDS = 3.0
MAX_SECONDS = 120.0  # upper limit of AnnouncementSpec.target_seconds


def seconds_for(text: str) -> float:
    """Expected speaking time of a text, kept inside the contract's limits."""
    seconds = len(text.split()) / WORDS_PER_SECOND
    return min(MAX_SECONDS, max(MIN_SECONDS, seconds))
