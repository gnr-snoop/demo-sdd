"""Filesystem ImageStorage adapter (T057, Principle V, FR-014).

Writes/reads captured images at ``usuarios/<user-id>/pictures.jpg``. The
``usuarios/`` tree is bind-mounted so the path is identical inside and outside
the backend container (SC-007).
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

PICTURES_FILENAME = "pictures.jpg"


class FilesystemImageStorage:
    """ImageStorage port implementation over the local filesystem.

    ``root`` defaults to the current working directory (so ``usuarios/`` lives
    at the repo/bind-mount root). Override via the ``USUARIOS_ROOT`` env var or
    the ``root`` constructor argument.
    """

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            env_root = os.environ.get("USUARIOS_ROOT")
            root = Path(env_root) if env_root else Path.cwd()
        self._root = Path(root)
        self._usuarios = self._root / "usuarios"
        self._usuarios.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _coerce_uuid(user_id: object) -> uuid.UUID:
        return user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))

    def _user_dir(self, user_id: object) -> Path:
        return self._usuarios / str(self._coerce_uuid(user_id))

    def _path(self, user_id: object) -> Path:
        return self._user_dir(user_id) / PICTURES_FILENAME

    def store(self, user_id: object, image_bytes: bytes) -> str:
        path = self._path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        # Always forward-slash, platform-independent (matches contract/SC-007).
        return f"usuarios/{self._coerce_uuid(user_id)}/{PICTURES_FILENAME}"

    def read(self, user_id: object) -> bytes:
        return self._path(user_id).read_bytes()

    def delete(self, user_id: object) -> None:
        d = self._user_dir(user_id)
        if d.exists():
            shutil.rmtree(d)
