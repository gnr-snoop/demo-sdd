"""ModelDownloader — lazy fetch + atomic-rename cache for ``.onnx`` model files
(spec 008, FR-008/FR-009, research R-4).

``ensure(name, url) -> Path``:
  1. Cache hit (``<cache>/<model_name>`` exists) → return path (no network).
  2. Else download to ``<cache>/<model_name>.part`` via ``httpx`` (single attempt,
     configurable timeout, no retry).
  3. Atomic ``os.replace(part, final)`` → no partial file ever cached.
  4. A lone ``.part`` file (interrupted download) is treated as absent → re-fetch.
  5. On any ``httpx`` error / timeout → ``ModelUnavailableError`` (fail fast, FR-009).

``model_name`` is the **complete filename** (including the ``.onnx`` extension);
callers pass ``YUNET_MODEL_FILENAME`` / ``SFACE_MODEL_FILENAME`` which already end
in ``.onnx``. The cached file is therefore ``models/face_detection_yunet_2023mar.onnx``
(not ``.onnx.onnx``) so the offline pre-download path (FR-008 AC-4) and the
real-model integration suite's model-presence detection (SC-012) work as
documented (convergence F-001 / T042).

Integrity is verified by the adapter constructor's load-test (FR-009), not here.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from ...config import get_settings
from ...logging import get_logger
from .constants import ModelUnavailableError

logger = get_logger("face_insight.adapters.ml.model_downloader")


class ModelDownloader:
    """Fetch and cache ``.onnx`` model files in ``settings.models_dir``.

    The cache directory is created on first use. Downloads write to a ``.part``
    temp file and atomically rename on completion so a partial file is never
    treated as a valid cache entry (FR-008 edge case).
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = get_settings().models_dir
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def ensure(self, model_name: str, url: str) -> Path:
        """Return the path to ``<cache>/<model_name>``, downloading it from
        ``url`` on first use. Cache hits skip the network (FR-008 AC-2).

        ``model_name`` is the complete filename including extension (e.g.
        ``face_detection_yunet_2023mar.onnx``); it is used verbatim so no
        ``.onnx`` suffix is appended (convergence F-001 / T042).

        Raises ``ModelUnavailableError`` on network failure / timeout (FR-009).
        """
        final_path = self._cache_dir / model_name
        if final_path.exists():
            logger.info(
                "model_cache_hit",
                model_name=model_name,
                path=str(final_path),
            )
            return final_path

        part_path = self._cache_dir / f"{model_name}.part"
        # A lone .part (interrupted download) is treated as absent → re-fetch.
        if part_path.exists():
            try:
                part_path.unlink()
            except OSError:
                pass

        settings = get_settings()
        timeout = httpx.Timeout(
            connect=settings.model_download_connect_timeout,
            read=settings.model_download_read_timeout,
            write=120.0,
            pool=30.0,
        )

        logger.info(
            "model_download_start",
            model_name=model_name,
            url=url,
        )
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with open(part_path, "wb") as f:
                        for chunk in resp.iter_bytes(chunk_size=65536):
                            f.write(chunk)
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
            # Clean up the partial file on failure.
            if part_path.exists():
                try:
                    part_path.unlink()
                except OSError:
                    pass
            logger.error(
                "model_unavailable",
                model_name=model_name,
                url=url,
                error=str(exc),
            )
            raise ModelUnavailableError(model_name, url, detail=str(exc)) from exc

        # Atomic rename → no partial file ever cached (FR-008).
        os.replace(part_path, final_path)
        logger.info(
            "model_download_complete",
            model_name=model_name,
            path=str(final_path),
        )
        return final_path


__all__ = ["ModelDownloader"]
