"""MockImageStorage (T051b) — implements the ImageStorage port (SC-005).

Writes to a temp dir mirroring ``usuarios/<user-id>/pictures.jpg``
(data-model.md mock constants). Satisfies FR-010/SC-005 — every declared port
has a deterministic mock adapter.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

PICTURES_FILENAME = "pictures.jpg"


class MockImageStorage:
    """Filesystem-backed mock image storage under a temp dir.

    Layout: ``<root>/usuarios/<user-id>/pictures.jpg``. The root defaults to a
    fresh temp directory so tests never touch the real bind mount.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._owns_root = root is None
        self._root: Path = root if root is not None else Path(tempfile.mkdtemp(prefix="mock-img-"))
        self._usuarios = self._root / "usuarios"
        self._usuarios.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: object) -> Path:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        return self._usuarios / str(uid)

    def _path(self, user_id: object) -> Path:
        return self._user_dir(user_id) / PICTURES_FILENAME

    def store(self, user_id: object, image_bytes: bytes) -> str:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        # Return the relative path mirroring the documented convention
        # (always forward-slash, platform-independent).
        return f"usuarios/{self._coerce_uuid(user_id)}/{PICTURES_FILENAME}"

    def read(self, user_id: object) -> bytes:
        return self._path(user_id).read_bytes()

    def delete(self, user_id: object) -> None:
        d = self._user_dir(user_id)
        if d.exists():
            shutil.rmtree(d)

    @staticmethod
    def _coerce_uuid(user_id: object) -> uuid.UUID:
        return user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))

    def close(self) -> None:
        """Release the temp dir if we own it."""
        if self._owns_root and self._root.exists():
            shutil.rmtree(self._root, ignore_errors=True)
