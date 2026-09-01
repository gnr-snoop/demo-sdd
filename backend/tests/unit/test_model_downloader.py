"""Unit tests for ModelDownloader (spec 008, US4, FR-008/FR-009, research R-4).

Covers:
- Cache hit/reuse: second ``ensure()`` returns the cached path without network.
- Fail-fast: ``ModelUnavailableError`` on network failure/timeout.
- Atomic ``.part`` rename: no partial cache entry left on failure.
- Stale ``.part`` treated as absent → re-fetch.
- Regression (T042 / convergence F-001): ``model_name`` is the complete filename
  including ``.onnx`` — no double ``.onnx.onnx`` extension, and a pre-placed
  real model file is a cache hit (FR-008 AC-2/AC-4, SC-008, SC-012).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from face_insight.adapters.ml.constants import (
    ModelUnavailableError,
    YUNET_MODEL_FILENAME,
)
from face_insight.adapters.ml.model_downloader import ModelDownloader


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "models"
    d.mkdir()
    return d


def test_cache_hit_returns_path_without_network(cache_dir: Path):
    """FR-008 AC-2 / SC-008: a cached file is reused without a network fetch."""
    model_name = "test_model.onnx"
    final = cache_dir / model_name
    final.write_bytes(b"\x00\x01\x02fake-onnx")

    downloader = ModelDownloader(cache_dir=cache_dir)
    # Patch httpx.Client to ensure it is NOT called on a cache hit.
    with patch("face_insight.adapters.ml.model_downloader.httpx.Client") as mock_client:
        result = downloader.ensure(model_name, "https://example.com/model.onnx")
        mock_client.assert_not_called()

    assert result == final
    assert result.exists()


def test_download_writes_and_renames_atomically(cache_dir: Path):
    """FR-008: a successful download writes to .part then atomically renames."""
    model_name = "new_model.onnx"
    url = "https://example.com/new_model.onnx"
    fake_bytes = b"\x00\x01\x02\x03fake-onnx-content"

    downloader = ModelDownloader(cache_dir=cache_dir)

    # Mock httpx streaming response.
    class _FakeResponse:
        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=65536):
            yield fake_bytes

    class _FakeStream:
        def __enter__(self):
            return _FakeResponse()

        def __exit__(self, *args):
            return False

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return _FakeStream()

    with patch(
        "face_insight.adapters.ml.model_downloader.httpx.Client",
        return_value=_FakeClient(),
    ):
        result = downloader.ensure(model_name, url)

    assert result == cache_dir / model_name
    assert result.read_bytes() == fake_bytes
    # No .part file left (atomic rename).
    assert not (cache_dir / f"{model_name}.part").exists()


def test_network_failure_raises_model_unavailable(cache_dir: Path):
    """FR-009 / SC-010: network failure → ModelUnavailableError, no cached file."""
    import httpx

    model_name = "fail_model.onnx"
    url = "https://example.com/fail.onnx"
    downloader = ModelDownloader(cache_dir=cache_dir)

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            raise httpx.ConnectError("connection refused")

    with patch(
        "face_insight.adapters.ml.model_downloader.httpx.Client",
        return_value=_FakeClient(),
    ):
        with pytest.raises(ModelUnavailableError) as exc_info:
            downloader.ensure(model_name, url)

    assert exc_info.value.model_name == model_name
    # No final file cached, no .part left.
    assert not (cache_dir / model_name).exists()
    assert not (cache_dir / f"{model_name}.part").exists()


def test_stale_part_file_treated_as_absent(cache_dir: Path):
    """FR-008 edge case: a lone .part (interrupted download) is removed and
    re-fetched, not treated as a valid cache entry."""
    model_name = "stale_model.onnx"
    url = "https://example.com/stale.onnx"
    part = cache_dir / f"{model_name}.part"
    part.write_bytes(b"partial garbage")
    fake_bytes = b"\x00full-onnx"

    downloader = ModelDownloader(cache_dir=cache_dir)

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=65536):
            yield fake_bytes

    class _FakeStream:
        def __enter__(self):
            return _FakeResponse()

        def __exit__(self, *args):
            return False

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return _FakeStream()

    with patch(
        "face_insight.adapters.ml.model_downloader.httpx.Client",
        return_value=_FakeClient(),
    ):
        result = downloader.ensure(model_name, url)

    assert result.read_bytes() == fake_bytes
    assert not part.exists()


def test_cache_dir_created_if_absent(tmp_path: Path):
    """The cache directory is created on first use."""
    d = tmp_path / "nested" / "models"
    assert not d.exists()
    ModelDownloader(cache_dir=d)
    assert d.is_dir()


# --- Regression: no double .onnx extension (T042 / convergence F-001) --------


def test_real_yunet_filename_no_double_extension(cache_dir: Path):
    """T042 / F-001: ``ensure()`` must treat ``model_name`` as the complete
    filename. The real ``YUNET_MODEL_FILENAME`` already ends in ``.onnx``, so the
    cached path must be ``models/face_detection_yunet_2023mar.onnx`` — NOT
    ``.onnx.onnx`` (FR-008 AC-2/AC-4, SC-008, SC-012).
    """
    assert YUNET_MODEL_FILENAME.endswith(".onnx")
    assert not YUNET_MODEL_FILENAME.endswith(".onnx.onnx")

    downloader = ModelDownloader(cache_dir=cache_dir)
    fake_bytes = b"\x00\x01\x02fake-yunet-onnx"

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=65536):
            yield fake_bytes

    class _FakeStream:
        def __enter__(self):
            return _FakeResponse()

        def __exit__(self, *args):
            return False

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            return _FakeStream()

    with patch(
        "face_insight.adapters.ml.model_downloader.httpx.Client",
        return_value=_FakeClient(),
    ):
        result = downloader.ensure(YUNET_MODEL_FILENAME, "https://example.com/yunet.onnx")

    expected = cache_dir / YUNET_MODEL_FILENAME
    assert result == expected
    # The cached file must NOT carry a double extension.
    assert not result.name.endswith(".onnx.onnx")
    assert result.name == "face_detection_yunet_2023mar.onnx"
    assert result.read_bytes() == fake_bytes


def test_real_yunet_filename_preplaced_is_cache_hit(cache_dir: Path):
    """T042 / F-001: a pre-placed ``models/face_detection_yunet_2023mar.onnx``
    (offline pre-download, FR-008 AC-4) is a cache hit — no network fetch and
    the returned path matches the pre-placed file (SC-008, SC-012).
    """
    preplaced = cache_dir / YUNET_MODEL_FILENAME
    preplaced.write_bytes(b"\x00preplaced-onnx")

    downloader = ModelDownloader(cache_dir=cache_dir)
    with patch("face_insight.adapters.ml.model_downloader.httpx.Client") as mock_client:
        result = downloader.ensure(YUNET_MODEL_FILENAME, "https://example.com/yunet.onnx")
        mock_client.assert_not_called()

    assert result == preplaced
    assert result.name == "face_detection_yunet_2023mar.onnx"
    assert not result.name.endswith(".onnx.onnx")


# --- Spec 009 (T018/T019): mood/age model download reuse (FR-009, R-8) --------

from face_insight.adapters.ml.constants import (  # noqa: E402
    EMOTIEFF_MODEL_FILENAME,
    EMOTIEFF_MODEL_URL,
    MIVOLO_CHECKPOINT_FILENAME,
    MIVOLO_CHECKPOINT_URL,
    ModelCorruptError,
)


def test_emotieff_model_constants_have_url_and_filename():
    """T018: the EmotiEff model constants are populated for ModelDownloader."""
    assert EMOTIEFF_MODEL_FILENAME == "enet_b0_8_best_afew.onnx"
    assert EMOTIEFF_MODEL_URL.startswith("https://")


def test_mivolo_model_constants_have_url_and_filename():
    """T018: the MiVOLO checkpoint constants are populated for ModelDownloader."""
    assert MIVOLO_CHECKPOINT_FILENAME.endswith(".pth")
    assert MIVOLO_CHECKPOINT_URL.startswith("https://")


def test_emotieff_model_preplaced_is_cache_hit(cache_dir: Path):
    """T018/FR-009: a pre-placed EmotiEff model file is a cache hit (no network)."""
    preplaced = cache_dir / EMOTIEFF_MODEL_FILENAME
    preplaced.write_bytes(b"\x00preplaced-emotieff")
    downloader = ModelDownloader(cache_dir=cache_dir)
    with patch("face_insight.adapters.ml.model_downloader.httpx.Client") as mock_client:
        result = downloader.ensure(EMOTIEFF_MODEL_FILENAME, EMOTIEFF_MODEL_URL)
        mock_client.assert_not_called()
    assert result == preplaced


def test_mivolo_checkpoint_preplaced_is_cache_hit(cache_dir: Path):
    """T018/FR-009: a pre-placed MiVOLO checkpoint is a cache hit (no network)."""
    preplaced = cache_dir / MIVOLO_CHECKPOINT_FILENAME
    preplaced.write_bytes(b"\x00preplaced-mivolo")
    downloader = ModelDownloader(cache_dir=cache_dir)
    with patch("face_insight.adapters.ml.model_downloader.httpx.Client") as mock_client:
        result = downloader.ensure(MIVOLO_CHECKPOINT_FILENAME, MIVOLO_CHECKPOINT_URL)
        mock_client.assert_not_called()
    assert result == preplaced


def test_emotieff_download_failure_raises_model_unavailable(cache_dir: Path):
    """T019/FR-009/SC-010: EmotiEff model download failure → ModelUnavailableError
    naming the model file (before serving traffic)."""
    import httpx

    downloader = ModelDownloader(cache_dir=cache_dir)

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            raise httpx.ConnectError("refused")

    with patch(
        "face_insight.adapters.ml.model_downloader.httpx.Client",
        return_value=_FakeClient(),
    ):
        with pytest.raises(ModelUnavailableError) as exc_info:
            downloader.ensure(EMOTIEFF_MODEL_FILENAME, EMOTIEFF_MODEL_URL)
    assert exc_info.value.model_name == EMOTIEFF_MODEL_FILENAME


def test_mivolo_download_failure_raises_model_unavailable(cache_dir: Path):
    """T019/FR-009/SC-010: MiVOLO checkpoint download failure → ModelUnavailableError
    naming the checkpoint file."""
    import httpx

    downloader = ModelDownloader(cache_dir=cache_dir)

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url):
            raise httpx.ConnectError("refused")

    with patch(
        "face_insight.adapters.ml.model_downloader.httpx.Client",
        return_value=_FakeClient(),
    ):
        with pytest.raises(ModelUnavailableError) as exc_info:
            downloader.ensure(MIVOLO_CHECKPOINT_FILENAME, MIVOLO_CHECKPOINT_URL)
    assert exc_info.value.model_name == MIVOLO_CHECKPOINT_FILENAME


def test_model_corrupt_error_names_model():
    """T019/FR-009: ModelCorruptError names the model for an actionable message."""
    err = ModelCorruptError(EMOTIEFF_MODEL_FILENAME, detail="load failed")
    assert err.model_name == EMOTIEFF_MODEL_FILENAME
    assert EMOTIEFF_MODEL_FILENAME in str(err)
