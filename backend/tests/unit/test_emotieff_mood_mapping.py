"""Unit test for the AFEW 8-class → PRD §6.4 label mapping + low-confidence
override (spec 009, US1, FR-005/FR-006, research R-4/R-5).

Tests the pure ``AFEW_TO_PRD_LABEL_MAP`` constant and ``resolve_mood_label``
helper from ``constants.py`` — no heavy ML runtime required (FR-013/R-9).
"""

from __future__ import annotations

import pytest

from face_insight.adapters.ml import (
    AFEW_INDEX_TO_EMOTION_NAME,
    AFEW_TO_PRD_LABEL_MAP,
    DEFAULT_MOOD_CONFIDENCE_THRESHOLD,
    resolve_mood_label,
)

# PRD §6.4 label set.
_PRD_LABELS = frozenset({"neutral", "feliz", "triste", "sorprendido", "no concluyente"})


def test_afew_map_covers_all_8_classes():
    """FR-005: the map covers exactly the 8 AFEW classes (0-7)."""
    assert set(AFEW_TO_PRD_LABEL_MAP) == set(range(8))


def test_afew_map_values_are_prd_labels():
    """FR-005: every mapped value is a member of the PRD §6.4 label set."""
    for idx, label in AFEW_TO_PRD_LABEL_MAP.items():
        assert label in _PRD_LABELS, f"index {idx} maps to non-PRD label {label!r}"


def test_afew_map_emotion_to_prd_semantics():
    """FR-005: Neutral→neutral, Happy→feliz, Sad→triste, Surprise→sorprendido,
    and Anger/Contempt/Disgust/Fear→no concluyente (per the hsemotion-onnx
    library's ``idx_to_class`` ordering for ``enet_b0_8_best_afew``)."""
    expected = {
        "Anger": "no concluyente",
        "Contempt": "no concluyente",
        "Disgust": "no concluyente",
        "Fear": "no concluyente",
        "Happiness": "feliz",
        "Neutral": "neutral",
        "Sadness": "triste",
        "Surprise": "sorprendido",
    }
    for idx, emotion_name in AFEW_INDEX_TO_EMOTION_NAME.items():
        assert AFEW_TO_PRD_LABEL_MAP[idx] == expected[emotion_name], (
            f"AFEW index {idx} ({emotion_name}) → "
            f"{AFEW_TO_PRD_LABEL_MAP[idx]!r}, expected {expected[emotion_name]!r}"
        )


def test_afew_index_to_emotion_name_covers_8():
    assert set(AFEW_INDEX_TO_EMOTION_NAME) == set(range(8))
    assert len(set(AFEW_INDEX_TO_EMOTION_NAME.values())) == 8


def test_default_mood_confidence_threshold():
    """FR-006/R-5: default threshold is 0.5."""
    assert DEFAULT_MOOD_CONFIDENCE_THRESHOLD == 0.5


# --- Low-confidence override (FR-006) ---------------------------------------
@pytest.mark.parametrize(
    "pred_index, top1_prob, threshold, expected_label",
    [
        # High confidence → mapped label passes through.
        (4, 0.9, 0.5, "feliz"),       # Happiness
        (5, 0.8, 0.5, "neutral"),     # Neutral
        (6, 0.7, 0.5, "triste"),      # Sadness
        (7, 0.6, 0.5, "sorprendido"),  # Surprise
        # Unmapped AFEW classes → no concluyente regardless of confidence.
        (0, 0.99, 0.5, "no concluyente"),  # Anger
        (1, 0.99, 0.5, "no concluyente"),  # Contempt
        (2, 0.99, 0.5, "no concluyente"),  # Disgust
        (3, 0.99, 0.5, "no concluyente"),  # Fear
        # Low confidence → no concluyente even for a PRD-mapped class.
        (4, 0.3, 0.5, "no concluyente"),   # Happiness but low prob
        (5, 0.49, 0.5, "no concluyente"),  # Neutral but just below threshold
        # Boundary: prob == threshold → NOT overridden (strict <).
        (4, 0.5, 0.5, "feliz"),
        (5, 0.5, 0.5, "neutral"),
        # Threshold = 0 → nothing overridden (prob >= 0 always).
        (0, 0.0, 0.0, "no concluyente"),  # Anger → no concluyente by mapping
        (4, 0.0, 0.0, "feliz"),           # Happiness, prob 0, threshold 0 → passes
    ],
)
def test_resolve_mood_label(pred_index, top1_prob, threshold, expected_label):
    """FR-005/FR-006: ``resolve_mood_label`` maps AFEW→PRD and applies the
    low-confidence override (strict ``<`` comparison)."""
    assert resolve_mood_label(pred_index, top1_prob, threshold) == expected_label


def test_resolve_mood_label_low_confidence_returns_no_conclusive():
    """FR-006 US1 AC-2: top-1 prob < threshold → 'no concluyente'."""
    for idx in range(8):
        assert resolve_mood_label(idx, 0.1, 0.5) == "no concluyente"
