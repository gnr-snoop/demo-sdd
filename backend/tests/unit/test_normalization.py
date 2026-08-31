"""Unit test for identifier normalization reuse (T046, spec 003 US6, FR-019).

Verifies trim + lowercase normalization and case-insensitive lookup — the
reuse of spec 002's ``normalize_identifier`` by the login use-case.
"""

from __future__ import annotations

import pytest

from face_insight.domain.validation import is_valid_identifier, normalize_identifier


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("demo@example.com", "demo@example.com"),
        ("  demo@example.com  ", "demo@example.com"),
        ("Demo@Example.COM", "demo@example.com"),
        ("  Demo@Example.COM  ", "demo@example.com"),
        ("User.Name", "user.name"),
        ("  MixedCase  ", "mixedcase"),
    ],
)
def test_normalize_identifier_trims_and_lowercases(raw, expected):
    assert normalize_identifier(raw) == expected


def test_normalize_identifier_type_error_on_non_string():
    with pytest.raises(TypeError):
        normalize_identifier(123)  # type: ignore[arg-type]


def test_case_insensitive_lookup_equivalence():
    """Two identifiers that differ only in case normalize to the same value,
    enabling case-insensitive lookup against the canonical stored form."""
    a = normalize_identifier("Demo@Example.com")
    b = normalize_identifier("demo@example.COM")
    assert a == b


def test_is_valid_identifier_accepts_email_and_username():
    assert is_valid_identifier("demo@example.com")
    assert is_valid_identifier("user.name")
    assert is_valid_identifier("  Demo@Example.com  ")


def test_is_valid_identifier_rejects_invalid():
    assert not is_valid_identifier("")
    assert not is_valid_identifier("   ")
    assert not is_valid_identifier("not valid!")
    assert not is_valid_identifier(123)  # type: ignore[arg-type]
