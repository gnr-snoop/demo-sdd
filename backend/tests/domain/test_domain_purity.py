"""SC-004 static check (T065/T036/T012): the domain layer has zero infra/ML imports.

Inspects ``backend/src/face_insight/domain/`` source for forbidden imports.

``image_handling.py`` is intentionally EXCLUDED: it is a domain-adjacent
service that imports Pillow (PIL) for decode/resize (R-3, FR-010). The pure
onboarding/login decision logic lives in ``onboarding.py`` / ``login.py`` and
invokes image handling through the route adapter, so the domain decision core
remains pure. This exclusion is documented here per T036 (FR-017, SC-007).

Spec 003 (T012) extends the gate to cover the new domain modules
``login.py``, ``comparison.py``, ``exceptions.py`` and the ``AuthSession``
session factories in ``entities.py``. The parametrize over ``*.py`` already
sweeps them; this module additionally asserts (a) the new files exist and
(b) no real-ML-model import (torch/ultralytics/cv2/opencv/numpy) leaks into
the domain (F-004 domain purity extension).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "face_insight" / "domain"

# Domain-adjacent modules excluded from the purity gate (with justification).
# - image_handling.py: imports Pillow for decode/resize (R-3). Pure decision
#   logic in onboarding.py / login.py calls it via the route adapter, not directly.
PURE_EXCLUSIONS = {"image_handling.py"}

# Spec 003 (T012): new domain modules that MUST exist and be pure after Phase 2.
# ``login.py`` is created in Phase 3 (T016); the parametrize purity sweep covers
# it automatically once it exists. This set asserts the Phase 2 foundations.
SPEC_003_DOMAIN_MODULES = {
    "comparison.py",
    "exceptions.py",
    "entities.py",
}

# Spec 004 (T008): new domain module that MUST exist and be pure. ``mood.py``
# holds the MoodService use-case + normalize_mood_label and must import only
# ports/result types/exceptions/stdlib (FR-015/SC-009). The parametrize purity
# sweep covers it automatically once it exists; this set asserts existence.
SPEC_004_DOMAIN_MODULES = {
    "mood.py",
}

FORBIDDEN_PREFIXES = (
    "face_insight.adapters",
    "face_insight.api",
    "sqlalchemy",
    "alembic",
    "psycopg",
    "asyncpg",
    "fastapi",
    "itsdangerous",
    "yolo",
    "ultralytics",
    "torch",
    "cv2",
    "opencv",
    "numpy",
    "PIL",
)

# Real ML model libraries — must never be imported by the domain (F-004).
REAL_ML_PREFIXES = (
    "torch",
    "ultralytics",
    "yolo",
    "cv2",
    "opencv",
    "numpy",
    "insightface",
    "facenet_pytorch",
    "dlib",
)


def _imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def test_domain_directory_exists():
    assert DOMAIN_DIR.is_dir(), f"domain dir not found: {DOMAIN_DIR}"


@pytest.mark.parametrize("module", sorted(SPEC_003_DOMAIN_MODULES))
def test_spec_003_domain_module_exists(module: str):
    """T012: the new spec 003 domain modules exist and are covered by the purity gate."""
    assert (DOMAIN_DIR / module).is_file(), f"missing domain module: {module}"


@pytest.mark.parametrize("module", sorted(SPEC_004_DOMAIN_MODULES))
def test_spec_004_domain_module_exists(module: str):
    """T008: the new spec 004 domain module (mood.py) exists and is covered by
    the purity gate (FR-015/SC-009 — port-only deps)."""
    assert (DOMAIN_DIR / module).is_file(), f"missing domain module: {module}"


@pytest.mark.parametrize("pyfile", sorted(DOMAIN_DIR.glob("*.py")))
def test_domain_has_no_infra_or_ml_imports(pyfile: Path):
    if pyfile.name in PURE_EXCLUSIONS:
        pytest.skip(f"{pyfile.name} is a documented domain-adjacent exclusion (T036)")
    source = pyfile.read_text(encoding="utf-8")
    modules = _imported_modules(source)
    offenders = {m for m in modules if any(m.startswith(p) or m == p for p in FORBIDDEN_PREFIXES)}
    assert not offenders, f"{pyfile.name} imports forbidden modules: {offenders}"


@pytest.mark.parametrize("pyfile", sorted(DOMAIN_DIR.glob("*.py")))
def test_domain_has_no_real_ml_imports(pyfile: Path):
    """F-004: no real-ML-model import leaks into the domain (mocks only — SC-012)."""
    if pyfile.name in PURE_EXCLUSIONS:
        pytest.skip(f"{pyfile.name} is a documented domain-adjacent exclusion (T036)")
    source = pyfile.read_text(encoding="utf-8")
    modules = _imported_modules(source)
    offenders = {m for m in modules if any(m.startswith(p) or m == p for p in REAL_ML_PREFIXES)}
    assert not offenders, f"{pyfile.name} imports real ML models: {offenders}"
