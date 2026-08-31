"""CosineComparison adapter (spec 003, R-1, T006).

Pure-Python cosine similarity: ``(a·b) / (||a|| · ||b||)``. No numpy in the
domain (Constitution Principle VII). A dimension mismatch raises
``ComparisonError`` (mapped to ``internal_error`` → 500 by the use-case).

This module lives under ``domain/`` because it is pure-Python (math only) and
contains no infra/ML imports — it is a domain-internal adapter for the
``Comparison`` port, swappable for a numpy-backed adapter in Fase 5 without
touching the login use-case (FR-021).
"""

from __future__ import annotations

import math

from .exceptions import ComparisonError
from .ports import Comparison


class CosineComparison(Comparison):
    """Cosine similarity over two equal-length float vectors.

    Returns a float in [-1, 1]. Raises ``ComparisonError`` on dimension
    mismatch or zero-norm vectors (which would make the similarity undefined).
    """

    def compare(self, a: list[float], b: list[float]) -> float:
        if a is None or b is None:
            raise ComparisonError("nil vector")
        if len(a) != len(b):
            raise ComparisonError(
                f"dimension mismatch: len(a)={len(a)} len(b)={len(b)}"
            )
        if not a:
            raise ComparisonError("empty vector")

        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for x, y in zip(a, b):
            dot += x * y
            norm_a += x * x
            norm_b += y * y

        if norm_a == 0.0 or norm_b == 0.0:
            raise ComparisonError("zero-norm vector")

        return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


__all__ = ["CosineComparison"]
