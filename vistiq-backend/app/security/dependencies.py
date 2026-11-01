"""
FastAPI dependencies for authentication and CSRF protection — Phase 4.

Kept separate from both the route handlers (app/routes/*.py) and the lower-
level session/password mechanics (app/security/sessions.py,
app/security/passwords.py) — this file only wires "an HTTP request" to
"an authenticated User," and nothing else.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.security.sessions import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, SESSION_COOKIE_NAME, get_valid_session


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Raises 401 for anything that isn't a valid, non-expired session —
    missing cookie, unknown token, and expired token are all
    indistinguishable to the caller on purpose (never reveal which one it
    was)."""
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    session = get_valid_session(db, raw_token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    user = db.get(User, session.user_id)
    if user is None:
        # The session's user no longer exists — treat exactly like any
        # other invalid session rather than a 500.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    return user


def require_csrf(request: Request, _current_user: User = Depends(get_current_user)) -> None:
    """Double-submit CSRF check for state-changing requests (POST/PUT/
    DELETE). A cross-site attacker page can make the browser send the
    session cookie automatically, but it cannot READ the (non-HttpOnly)
    CSRF cookie to also set the matching header — same-origin policy
    blocks that — so a mismatch (or a missing header entirely) means the
    request didn't genuinely originate from VISTIQ's own frontend.

    Depends on `get_current_user` (even though it doesn't need the user
    object itself) deliberately, not just to require a session, but to
    force FastAPI to resolve authentication FIRST — without this, an
    entirely unauthenticated request (no cookies at all) would fail the
    CSRF check before ever reaching the authentication check, surfacing a
    confusing 403 instead of the correct 401.

    Applied only to already-authenticated, state-changing routes — not to
    /auth/login or /auth/register themselves, which have no prior session
    to protect (standard practice; see app/routes/auth.py's module
    docstring for the one known limitation this leaves: login CSRF)."""
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_value or not header_value or cookie_value != header_value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid.")
