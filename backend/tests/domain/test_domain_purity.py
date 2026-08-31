"""SC-004 static check (T065): the domain layer has zero infra/ML imports.

Inspects ``backend/src/face_insight/domain/`` source for forbidden imports.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "src" / "face_insight" / "domain"

FORBIDDEN_PREFIXES = (
    "face_insight.adapters",
    "face_insight.api",
    "sqlalchemy",
    "alembic",
    "psycopg",
    "asyncpg",
    "fastapi",
    "yolo",
    "ultralytics",
    "torch",
    "cv2",
    "opencv",
    "numpy",
    "PIL",
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


@pytest.mark.parametrize("pyfile", sorted(DOMAIN_DIR.glob("*.py")))
def test_domain_has_no_infra_or_ml_imports(pyfile: Path):
    source = pyfile.read_text(encoding="utf-8")
    modules = _imported_modules(source)
    offenders = {m for m in modules if any(m.startswith(p) or m == p for p in FORBIDDEN_PREFIXES)}
    assert not offenders, f"{pyfile.name} imports forbidden modules: {offenders}"
