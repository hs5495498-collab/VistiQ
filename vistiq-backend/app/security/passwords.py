"""
Password hashing and email normalization — Phase 4.

Hashing vs. encryption, explicitly: encryption is reversible (you can
decrypt ciphertext back to plaintext given the right key) — passwords must
NEVER be stored that way, because anyone who gets the key (or breaks it)
recovers every real password. Hashing is one-way: `hash_password()` can
never be reversed back into the original password, even by VISTIQ itself.
Verifying a login means re-hashing the submitted password and comparing
hashes (`verify_password()`), never decrypting anything.

Argon2id specifically (via the maintained `argon2-cffi` library, never a
hand-rolled algorithm) is a memory-hard hash: deliberately slow and
memory-expensive to compute, so that even if the `password_hash` column
were ever stolen, brute-forcing it is expensive per guess — unlike a fast
hash (MD5/SHA-256), which is exactly correct for a session token (see
app/security/sessions.py) but wrong for a password, since a fast hash lets
an attacker try billions of guesses per second once they have the hash.
`PasswordHasher()` generates a fresh random salt per password automatically
and embeds it in the returned hash string — never reused, never
hand-specified.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()

# Deliberately permissive but not meaningless — long enough to resist
# casual guessing, short enough not to frustrate a PBL demo. Configurable
# in one place, not scattered magic numbers.
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128  # Argon2 has no real upper bound; this just caps request-body size/abuse


def normalize_email(email: str) -> str:
    """Lowercase + stripped, so "A@B.com" and " a@b.com " are recognized
    as the same account rather than silently creating two."""
    return email.strip().lower()


def validate_password_strength(password: str) -> list[str]:
    """Returns a list of human-readable problems — empty means valid.
    Never raises; the caller decides how to present multiple problems at
    once (more useful than failing on only the first one found)."""
    problems: list[str] = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"Password must be at most {MAX_PASSWORD_LENGTH} characters long.")
    return problems


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Never raises — a malformed/corrupt stored hash or a wrong password
    both simply return False. Callers must not use this to distinguish
    "wrong password" from "account doesn't exist"; see app/routes/auth.py's
    login endpoint, which always returns the same generic error either
    way."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False
