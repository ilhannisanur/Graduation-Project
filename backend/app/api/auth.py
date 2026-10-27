from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.users import UserRow, service
from app.users.schemas import LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth")

COOKIE_NAME = "radio_auth"
COOKIE_PATH = "/api"


def clear_login_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, httponly=True, samesite="lax")


def _set_login_cookie(response: Response, token: str) -> None:
    # HttpOnly: page scripts cannot read it. SameSite=Lax: other sites cannot make the browser
    # send it with POST/PUT/DELETE, which covers CSRF for our state-changing endpoints.
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=service.SESSION_DAYS * 24 * 60 * 60,
        path=COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
    )


def optional_user(
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> UserRow | None:
    """The logged-in user, or None for a guest. Never trusts a user id sent by the client."""
    return service.user_for_token(db, token) if token else None


def current_user(user: UserRow | None = Depends(optional_user)) -> UserRow:
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


def user_out(user: UserRow) -> UserOut:
    return UserOut(id=user.id, username=user.username, created_at=user.created_at)


@router.post("/register", status_code=201)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> UserOut:
    try:
        user = service.register(db, body.username, body.password, body.preference_learning)
    except service.UsernameTaken:
        raise HTTPException(status_code=409, detail="This username is taken") from None
    token = service.start_session(db, user)
    db.commit()
    db.refresh(user)
    _set_login_cookie(response, token)
    return user_out(user)


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = service.authenticate(db, body.username, body.password)
    if user is None:
        # One message for both cases, so it does not tell which usernames exist.
        raise HTTPException(status_code=401, detail="Wrong username or password")
    token = service.start_session(db, user)
    db.commit()
    _set_login_cookie(response, token)
    return user_out(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> None:
    if token:
        service.end_session(db, token)
        db.commit()
    clear_login_cookie(response)
