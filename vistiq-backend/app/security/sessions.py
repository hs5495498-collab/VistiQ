"""
Opaque session tokens and cookie configuration — Phase 4.

Why a fast hash (SHA-256) here but Argon2id for passwords
(app/security/passwords.py): a session token is already 256 bits of
`secrets`-module randomness — maximal entropy, nothing to brute-force
cheaply even with a fast hash. A password is low-entropy, human-chosen
text, where a fast hash would let an attacker who steals the hash try
billions of guesses per second; a deliberately slow, memory-hard hash is
what makes that expensive. Using Argon2id for a token would only add
needless CPU cost with no corresponding security benefit.

Only `token_hash` (the SHA-256 digest) is ever written to the database —
the raw token exists only in the user's HttpOnly cookie and this request's
memory. A stolen database can never be turned back into a valid session.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DBSession

from app.database.models import UserSession

SESSION_TOKEN_BYTES = 32  # 256 bits
SESSION_TTL_DAYS = 7

SESSION_COOKIE_NAME = "vistiq_session"
CSRF_COOKIE_NAME = "vistiq_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Cookie `Secure` MUST be env-driven, not hardcoded True: a Secure cookie
# is silently dropped by every browser over plain HTTP, which is exactly
# how this project's local dev server runs (http://127.0.0.1:8000) —
# hardcoding True would break login/session cookies for every local
# developer. Set VISTIQ_COOKIE_SECURE=true in any real HTTPS deployment.
COOKIE_SECURE = os.environ.get("VISTIQ_COOKIE_SECURE", "false").strip().lower() == "true"
COOKIE_SAMESITE = "lax"  # see app/routes/auth.py module docstring for why Lax, not Strict/None


def _generate_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: DBSession, user_id: int) -> tuple[str, datetime]:
    """Creates a brand-new session row (never reuses an existing one —
    this IS session rotation, the standard defense against session
    fixation: every successful login gets a fresh, unguessable identifier,
    so an attacker who fixed a pre-login session token gains nothing).
    Returns (raw_token, expires_at) — the raw token is what goes in the
    cookie; it is never stored anywhere."""
    token = _generate_token()
    expires_at = datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)
    db.add(UserSession(user_id=user_id, token_hash=_hash_token(token), expires_at=expires_at))
    db.commit()
    return token, expires_at


def get_valid_session(db: DBSession, raw_token: str | None) -> UserSession | None:
    """Returns the matching, non-expired session, or None for anything
    else (missing cookie, unknown token, expired session) — callers must
    treat all of those identically (unauthenticated), never distinguish
    them in an error message. An expired session is opportunistically
    deleted here (lazy cleanup — no scheduled job exists; see this
    project's documented limitations)."""
    if not raw_token:
        return None

    session = db.query(UserSession).filter(UserSession.token_hash == _hash_token(raw_token)).first()
    if session is None:
        return None
    if session.expires_at < datetime.utcnow():
        db.delete(session)
        db.commit()
        return None
    return session


def invalidate_session(db: DBSession, raw_token: str | None) -> None:
    """Logout. Silently does nothing for a missing/unknown token — logout
    must never error just because the session was already gone."""
    if not raw_token:
        return
    db.query(UserSession).filter(UserSession.token_hash == _hash_token(raw_token)).delete()
    db.commit()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)
