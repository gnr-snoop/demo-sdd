"""Unit tests for CosineComparison (T044, spec 003 US6, R-1).

Pure-Python cosine similarity: (a·b)/(||a||·||b||). Covers cosine values,
threshold boundary, and dimension-mismatch → ComparisonError.
"""

from __future__ import annotations

import math

import pytest

from face_insight.domain.comparison import CosineComparison
from face_insight.domain.exceptions import ComparisonError


def test_identical_vectors_similarity_1():
    cmp = CosineComparison()
    v = [0.1, 0.2, 0.3, 0.4]
    assert cmp.compare(v, v) == pytest.approx(1.0)


def test_orthogonal_vectors_similarity_0():
    cmp = CosineComparison()
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cmp.compare(a, b) == pytest.approx(0.0)


def test_opposite_vectors_similarity_minus_1():
    cmp = CosineComparison()
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert cmp.compare(a, b) == pytest.approx(-1.0)


def test_128_dim_constant_vector_similarity_1():
    """Mock embedding: 128-dim 0.1 vector vs itself → 1.0 (happy path)."""
    cmp = CosineComparison()
    v = [0.1] * 128
    assert cmp.compare(v, v) == pytest.approx(1.0)


def test_128_dim_orthogonal_similarity_0():
    """Orthogonal 128-dim vector vs all-0.1 → 0.0 (below threshold → auth_failed)."""
    cmp = CosineComparison()
    template = [0.1] * 128
    capture = [0.0] * 128
    capture[0] = 0.1
    capture[1] = -0.1
    assert cmp.compare(capture, template) == pytest.approx(0.0)


def test_threshold_boundary():
    """similarity == threshold is accepted (>= operator, FR-003)."""
    cmp = CosineComparison()
    v = [0.1] * 128
    sim = cmp.compare(v, v)
    assert sim >= 0.5  # accepted
    assert sim >= 1.0  # boundary: exactly 1.0


def test_dimension_mismatch_raises_comparison_error():
    cmp = CosineComparison()
    a = [0.1] * 128
    b = [0.1] * 127
    with pytest.raises(ComparisonError):
        cmp.compare(a, b)


def test_empty_vectors_raises_comparison_error():
    cmp = CosineComparison()
    with pytest.raises(ComparisonError):
        cmp.compare([], [])


def test_zero_norm_raises_comparison_error():
    cmp = CosineComparison()
    with pytest.raises(ComparisonError):
        cmp.compare([0.0, 0.0], [1.0, 1.0])


def test_known_cosine_value():
    """cos(45°) ≈ 0.7071."""
    cmp = CosineComparison()
    a = [1.0, 0.0]
    b = [1.0, 1.0]
    assert cmp.compare(a, b) == pytest.approx(math.cos(math.radians(45)), rel=1e-6)
