from datetime import datetime

from app.contracts import ListenerContext
from app.users.models import UserProfileRow


def listener_context(
    profile: UserProfileRow, local_time: datetime, weather_summary: str | None = None
) -> ListenerContext:
    """The only way profile data reaches DJ Brain and the LLM.

    It takes the profile, not the account, so the username, user id and password hash cannot
    end up in a prompt. Artists are left out too: names can be personal (a friend's band).
    """
    return ListenerContext(
        local_time=local_time,
        city=profile.weather_city,
        weather_summary=weather_summary,
        preferred_genres=list(profile.genres),
        news_topics=list(profile.news_topics),
    )
