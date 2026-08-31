"""Unit tests for identifier validation + normalization (T020, R-1, FR-002)."""

from __future__ import annotations

import pytest

from face_insight.domain.validation import is_valid_identifier, normalize_identifier


# --- normalize_identifier --------------------------------------------------
def test_normalize_trims_and_lowercases():
    assert normalize_identifier("  Demo@Example.COM  ") == "demo@example.com"


def test_normalize_idempotent_on_already_normalized():
    assert normalize_identifier("demo@example.com") == "demo@example.com"


def test_normalize_username_lowercases():
    assert normalize_identifier("  AliceDoe  ") == "alicedoe"


def test_normalize_rejects_non_string():
    with pytest.raises(TypeError):
        normalize_identifier(123)  # type: ignore[arg-type]


# --- is_valid_identifier: empty / whitespace -------------------------------
@pytest.mark.parametrize("raw", ["", "   ", "\t", "\n  "])
def test_invalid_empty_or_whitespace(raw):
    assert not is_valid_identifier(raw)


def test_invalid_non_string():
    assert not is_valid_identifier(None)
    assert not is_valid_identifier(123)


# --- is_valid_identifier: email branch -------------------------------------
@pytest.mark.parametrize(
    "raw",
    ["demo@example.com", "user.name@sub.domain.org", "a@b.co", "  Demo@Example.COM  "],
)
def test_valid_emails(raw):
    assert is_valid_identifier(raw)


@pytest.mark.parametrize("raw", ["plainaddress", "no-at-sign", "user_name", "a.b-c"])
def test_valid_usernames_that_are_not_emails(raw):
    # These match the username branch (email-or-username union) → valid.
    assert is_valid_identifier(raw)


@pytest.mark.parametrize("raw", ["@no-local.com", "a@b", "a@.com", "a b@c.com", "café"])
def test_invalid_identifiers(raw):
    assert not is_valid_identifier(raw)


# --- is_valid_identifier: username branch ----------------------------------
@pytest.mark.parametrize("raw", ["abc", "a_b-c.d", "User123", "x" * 32])
def test_valid_usernames(raw):
    assert is_valid_identifier(raw)


@pytest.mark.parametrize("raw", ["ab", "x" * 33, "has space", "bad!char", "café"])
def test_invalid_usernames(raw):
    assert not is_valid_identifier(raw)


# --- Boundary lengths (3 and 32 chars) -------------------------------------
def test_username_min_length_3():
    assert is_valid_identifier("abc")
    assert not is_valid_identifier("ab")


def test_username_max_length_32():
    assert is_valid_identifier("a" * 32)
    assert not is_valid_identifier("a" * 33)


# --- Normalization does not change validity --------------------------------
def test_normalized_value_still_valid_for_email():
    raw = "  Demo@Example.COM  "
    assert is_valid_identifier(raw)
    assert is_valid_identifier(normalize_identifier(raw))
