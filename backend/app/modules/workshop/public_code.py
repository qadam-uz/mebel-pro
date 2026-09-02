"""The workshop's public link code — generation, normalization, allocation.

`Workshop.public_code` is what `/w/{code}` carries: the identifier a client
scans off a counter QR or a business card. It is **not** a secret — it resolves
to information a client could already read on the shop's door — but it has to be
unguessable enough that the public resolve endpoint can't be walked, so it is
drawn from `secrets` over Crockford base32 (32^8 ≈ 1.1e12) and the endpoint is
rate-limited on top.

Crockford's alphabet drops `I`, `L`, `O` and `U`, which is what makes a code
survive being read off a printed sheet and typed back in; `normalize` folds the
lookalikes a human still types (`I`/`l` → `1`, `O` → `0`) and the separators a
human still inserts.

The code is permanent: printed QR codes must never rot, so nothing in this
module rewrites an allocated code.
"""

import re
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Crockford base32: digits + uppercase letters minus I, L, O, U.
PUBLIC_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PUBLIC_CODE_LENGTH = 8

# Lookalikes a person typing a printed code produces, folded to the character
# the alphabet actually holds.
_LOOKALIKES = str.maketrans({"I": "1", "L": "1", "O": "0", "U": "V"})
_SEPARATORS = re.compile(r"[\s\-_]+")


def generate_public_code() -> str:
    """A fresh random code. Uniqueness is the database's job (see `allocate`)."""
    return "".join(secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(PUBLIC_CODE_LENGTH))


def normalize_public_code(raw: str) -> str | None:
    """Fold a typed/scanned code to its canonical form, or `None` if it can't be one.

    Rejecting the malformed shapes here keeps the resolve endpoint from touching
    the database for input that could never match a row.
    """
    candidate = _SEPARATORS.sub("", raw).strip().upper().translate(_LOOKALIKES)
    if len(candidate) != PUBLIC_CODE_LENGTH:
        return None
    if any(char not in PUBLIC_CODE_ALPHABET for char in candidate):
        return None
    return candidate


async def allocate_public_code(db: AsyncSession) -> str:
    """A code no workshop holds yet.

    A collision is astronomically unlikely, but the column is unique and a
    provisioning request must not die on a coin flip — so the draw is retried a
    few times before the unique index becomes the (still correct) backstop.
    """
    # Imported here rather than at module import time: `models` imports this
    # module for the column default.
    from app.modules.workshop.models import Workshop

    for _ in range(5):
        code = generate_public_code()
        taken = await db.scalar(select(Workshop.id).where(Workshop.public_code == code).limit(1))
        if taken is None:
            return code
    return generate_public_code()
