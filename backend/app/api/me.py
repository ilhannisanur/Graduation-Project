from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import current_user, user_out
from app.db.session import get_db
from app.users import UserRow, service
from app.users.options import GENRES, LANGUAGES, NEWS_TOPICS
from app.users.schemas import Option, Profile, ProfileOptions, UserOut

router = APIRouter()


@router.get("/me")
def me(user: UserRow = Depends(current_user)) -> UserOut:
    return user_out(user)


@router.get("/me/profile")
def get_profile(user: UserRow = Depends(current_user), db: Session = Depends(get_db)) -> Profile:
    return service.profile_from_row(service.get_profile_row(db, user.id))


@router.put("/me/profile")
def put_profile(
    profile: Profile, user: UserRow = Depends(current_user), db: Session = Depends(get_db)
) -> Profile:
    row = service.update_profile(db, user.id, profile)
    db.commit()
    return service.profile_from_row(row)


def _options(choices: dict[str, str]) -> list[Option]:
    return [Option(value=value, label=label) for value, label in choices.items()]


@router.get("/profile/options")
def profile_options() -> ProfileOptions:
    """The fixed choices for the profile form; public, they contain nothing personal."""
    return ProfileOptions(
        genres=_options(GENRES), languages=_options(LANGUAGES), news_topics=_options(NEWS_TOPICS)
    )
