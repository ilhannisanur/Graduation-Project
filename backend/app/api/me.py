from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.auth import clear_login_cookie, current_user, user_out
from app.db.session import get_db
from app.radio.planner import BroadcastPlanner, current_planner
from app.users import UserRow, service
from app.users.options import GENRES, LANGUAGES, NEWS_TOPICS
from app.users.privacy import CONSENT_KINDS, NOTICE, NOTICE_VERSION, PREFERENCE_LEARNING
from app.users.schemas import (
    ConsentState,
    ConsentsUpdate,
    DeleteAccountRequest,
    NoticeSection,
    Option,
    PrivacyNotice,
    Profile,
    ProfileOptions,
    UserOut,
)
from app.users.security import verify_password

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


# ------------------------------------------------------- privacy and consent


@router.get("/privacy")
def privacy_notice() -> PrivacyNotice:
    """What is stored and why; public so it can be read before signing up."""
    return PrivacyNotice(
        version=NOTICE_VERSION,
        sections=[NoticeSection(title=title, text=text) for title, text in NOTICE],
        consents=CONSENT_KINDS,
    )


def _consent_states(db: Session, user_id: str) -> dict[str, ConsentState]:
    return {
        kind: ConsentState(
            description=CONSENT_KINDS[kind],
            granted=bool(row and row.granted),
            notice_version=row.notice_version if row else None,
            updated_at=row.created_at if row else None,
        )
        for kind, row in service.current_consents(db, user_id).items()
    }


@router.get("/me/consents")
def get_consents(
    user: UserRow = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, ConsentState]:
    return _consent_states(db, user.id)


@router.put("/me/consents")
def put_consents(
    body: ConsentsUpdate, user: UserRow = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, ConsentState]:
    current = service.current_consents(db, user.id)[PREFERENCE_LEARNING]
    # A new row only when the choice changes, so the history stays readable.
    if current is None or current.granted != body.preference_learning:
        service.record_consent(db, user.id, PREFERENCE_LEARNING, body.preference_learning)
        db.commit()
    return _consent_states(db, user.id)


# ------------------------------------------------------- the listener's data


@router.get("/me/data")
def download_my_data(
    user: UserRow = Depends(current_user), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(
        service.export_user_data(db, user),
        headers={"Content-Disposition": 'attachment; filename="my-radio-data.json"'},
    )


@router.delete("/me", status_code=204)
def delete_my_account(
    body: DeleteAccountRequest,
    response: Response,
    user: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
    planner: BroadcastPlanner | None = Depends(current_planner),
) -> None:
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(status_code=403, detail="Wrong password")
    user_id = user.id
    service.delete_account(db, user_id)
    db.commit()
    if planner is not None:  # listening sessions live in memory, not in the database
        planner.close_user_sessions(user_id)
    clear_login_cookie(response)
