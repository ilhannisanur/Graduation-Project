import hashlib
import secrets
from functools import cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# argon2id with the library defaults (RFC 9106 low-memory profile); OWASP's first choice.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the hash was made with older settings and should be upgraded at login."""
    return _hasher.check_needs_rehash(password_hash)


@cache
def dummy_hash() -> str:
    """Checked against when the username does not exist, so a failed login takes the same
    time either way and does not reveal which usernames are registered."""
    return hash_password(secrets.token_urlsafe(16))


def new_session_token() -> str:
    return secrets.token_urlsafe(32)  # 256 random bits


def token_hash(token: str) -> str:
    # A fast hash is enough here: the token is random, so it cannot be guessed or brute-forced
    # the way a password can.
    return hashlib.sha256(token.encode()).hexdigest()
