"""Security primitives — password hashing, opaque session tokens, complexity.

Sessions are opaque DB-backed tokens (not JWTs): a random 32-byte string handed
to the client, stored only as its SHA-256 hash. The plaintext is never
persisted, so the DB row is the source of truth and deleting it logs the device
out instantly (docs/ref/entities/identity.md).
"""

import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()

# Password complexity: ≥ 8 chars, with at least one upper, one lower, one digit.
_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
MIN_PASSWORD_LENGTH = 8


def hash_password(plaintext: str) -> str:
    """Return an argon2 hash for ``plaintext``."""
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, password_hash: str) -> bool:
    """Constant-time-ish verify; ``False`` on mismatch or a malformed hash."""
    try:
        return _hasher.verify(password_hash, plaintext)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses outdated argon2 parameters."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def password_complexity_ok(plaintext: str) -> bool:
    """Enforce the v1 complexity policy."""
    return (
        len(plaintext) >= MIN_PASSWORD_LENGTH
        and bool(_UPPER.search(plaintext))
        and bool(_LOWER.search(plaintext))
        and bool(_DIGIT.search(plaintext))
    )


def generate_token() -> str:
    """A fresh opaque token — 32 random bytes, URL-safe."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 hex digest of an opaque token (what we store / look up by)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_temp_password() -> str:
    """A readable temp password that satisfies the complexity policy."""
    alphabet_lower = "abcdefghijkmnpqrstuvwxyz"
    alphabet_upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    pick = [
        secrets.choice(alphabet_upper),
        secrets.choice(alphabet_lower),
        secrets.choice(digits),
    ]
    pool = alphabet_lower + alphabet_upper + digits
    pick += [secrets.choice(pool) for _ in range(7)]
    secrets.SystemRandom().shuffle(pick)
    return "".join(pick)
