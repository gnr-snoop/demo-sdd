"""License provenance test for concrete ML models (spec 008 + spec 009,
F-001, FR-004, Constitution Principle III).

Asserts all concrete models carry OSI-approved open-source license constants.
"""

from __future__ import annotations

from face_insight.adapters.ml import (
    EMOTIEFF_LICENSE,
    MIVOLO_LICENSE,
    SFACE_LICENSE,
    YUNET_LICENSE,
)

# OSI-approved open-source license SPDX identifiers (subset relevant here).
_OSI_APPROVED = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "GPL-3.0", "LGPL-3.0"}


def test_yunet_license_is_osi_approved():
    """FR-004 / Constitution Principle III: YuNet is MIT-licensed (open-source)."""
    assert YUNET_LICENSE == "MIT"
    assert YUNET_LICENSE in _OSI_APPROVED


def test_sface_license_is_osi_approved():
    """FR-004 / Constitution Principle III: SFace is Apache-2.0 (open-source)."""
    assert SFACE_LICENSE == "Apache-2.0"
    assert SFACE_LICENSE in _OSI_APPROVED


def test_emotieff_license_is_osi_approved():
    """Spec 009 (FR-004 / Constitution Principle III): EmotiEff/HSEmotion code
    + model is Apache-2.0 (open-source)."""
    assert EMOTIEFF_LICENSE == "Apache-2.0"
    assert EMOTIEFF_LICENSE in _OSI_APPROVED


def test_mivolo_license_is_osi_approved():
    """Spec 009 (FR-004 / Constitution Principle III / R-3): MiVOLO code is
    Apache-2.0 (open-source). The checkpoint is open-weights (research R-3; the
    port abstraction is the fallback if an incompatible checkpoint license is
    found at runtime)."""
    assert MIVOLO_LICENSE == "Apache-2.0"
    assert MIVOLO_LICENSE in _OSI_APPROVED


def test_production_verification_threshold_constant():
    """FR-016 / R-7: the production cosine threshold is 0.363 (OpenCV LFW)."""
    from face_insight.adapters.ml import PRODUCTION_VERIFICATION_THRESHOLD

    assert PRODUCTION_VERIFICATION_THRESHOLD == 0.363


def test_model_version_strings_distinct_from_mock():
    """FR-003: concrete model_version strings are distinct from the mock ones."""
    from face_insight.adapters.ml import EMOTIEFF_MODEL_VERSION, MIVOLO_MODEL_VERSION

    assert EMOTIEFF_MODEL_VERSION != "mock-mood-v1"
    assert MIVOLO_MODEL_VERSION != "mock-age-estimator-v1"
    assert EMOTIEFF_MODEL_VERSION != MIVOLO_MODEL_VERSION

