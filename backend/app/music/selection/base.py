from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.contracts import Emotion, Track


class NoTrackAvailable(Exception):
    """Raised when the catalog has no track to choose from."""


class TrackSelector(ABC):
    """Chooses the next song. The broadcast planner depends only on this interface.

    The selector keeps no state: the caller passes what was played in this session
    (oldest first), so any selector can be swapped in without migrating anything.
    """

    @abstractmethod
    def next_track(self, history: Sequence[Track], emotion: Emotion | None = None) -> Track:
        """Pick the next track. `emotion` is the mood of the moment, if known."""
