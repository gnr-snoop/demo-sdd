"""Identifier validation + normalization (spec 002, R-1, FR-002).

Pure functions: no infra/ML/SQLAlchemy/FastAPI imports. The identifier is
either a valid email or a username (3–32 chars from ``[a-zA-Z0-9._-]``).
Normalization is trim + lowercase (pinned decision).
"""

from __future__ import annotations

import re

# Email: non-empty local-part + @ + non-empty domain with a dot.
# (Pragmatic, not RFC-strict — matches the contract pattern.)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Username: 3–32 chars of letters, digits, '.', '_', '-'.
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,32}$")


def normalize_identifier(raw: str) -> str:
    """Normalize an identifier: trim whitespace and lowercase.

    The caller is expected to have validated the identifier via
    :func:`is_valid_identifier` first, but normalization is safe to apply
    unconditionally.
    """
    if not isinstance(raw, str):
        raise TypeError(f"identifier must be a str, got {type(raw).__name__}")
    return raw.strip().lower()


def is_valid_identifier(raw: object) -> bool:
    """Return True if ``raw`` is a valid email or username after trim.

    A valid identifier is non-empty after trim and matches either the email
    pattern or the username pattern (on the trimmed value, before lowercasing
    — lowercasing does not change validity for these patterns).
    """
    if not isinstance(raw, str):
        return False
    trimmed = raw.strip()
    if not trimmed:
        return False
    if _EMAIL_RE.match(trimmed) or _USERNAME_RE.match(trimmed):
        return True
    return False
