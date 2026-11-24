from datetime import datetime

from app.contracts import ListenerContext
from app.users.models import UserProfileRow


def listener_context(
    profile: UserProfileRow, local_time: datetime, weather_summary: str | None = None
) -> ListenerContext:
    """The only way profile data reaches DJ Brain and the LLM.

    It takes the profile, not the account, so the username, user id and password hash cannot
    end up in a prompt.
    """
    return ListenerContext(
        local_time=local_time,
        weather_summary=weather_summary,
        preferred_genres=list(profile.genres),
    )
