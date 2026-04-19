"""mapsi.builder.bindata 단위 테스트."""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from mapsi.builder.bindata import register_image


def _write_fake_image(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def test_register_image_copies_file_to_bindata_and_returns_manifest(tmp_path: Path) -> None:
    src = tmp_path / "figure.png"
    work_dir = tmp_path / "work"
    _write_fake_image(src, b"fake-png-data")

    binary_item_id, manifest_entry = register_image(str(src), str(work_dir))

    assert binary_item_id == "image1"
    assert manifest_entry == {
        "id": "image1",
        "href": "BinData/image1.png",
        "media-type": "image/png",
    }
    assert (work_dir / "BinData" / "image1.png").is_file()
    assert (work_dir / "BinData" / "image1.png").read_bytes() == b"fake-png-data"


def test_register_image_reuses_existing_file_when_content_matches(tmp_path: Path) -> None:
    src1 = tmp_path / "first.png"
    src2 = tmp_path / "second.png"
    work_dir = tmp_path / "work"

    payload = b"same-image-content"
    _write_fake_image(src1, payload)
    _write_fake_image(src2, payload)

    first_id, first_entry = register_image(str(src1), str(work_dir))
    second_id, second_entry = register_image(str(src2), str(work_dir))

    assert first_id == "image1"
    assert second_id == "image1"
    assert first_entry == second_entry

    files = list((work_dir / "BinData").glob("*"))
    assert len(files) == 1
    assert files[0].name == "image1.png"


def test_register_image_assigns_incrementing_ids_for_different_files(tmp_path: Path) -> None:
    src1 = tmp_path / "a.png"
    src2 = tmp_path / "b.jpg"
    work_dir = tmp_path / "work"

    _write_fake_image(src1, b"image-a")
    _write_fake_image(src2, b"image-b")

    first_id, first_entry = register_image(str(src1), str(work_dir))
    second_id, second_entry = register_image(str(src2), str(work_dir))

    assert first_id == "image1"
    assert second_id == "image2"

    assert first_entry["href"] == "BinData/image1.png"
    assert first_entry["media-type"] == "image/png"
    assert second_entry["href"] == "BinData/image2.jpg"
    assert second_entry["media-type"] == "image/jpeg"


def test_register_image_supports_decomposed_korean_filename(tmp_path: Path) -> None:
    nfd_name = unicodedata.normalize("NFD", "한글이미지.png")
    src = tmp_path / nfd_name
    work_dir = tmp_path / "work"

    _write_fake_image(src, b"korean-image-data")

    binary_item_id, manifest_entry = register_image(str(src), str(work_dir))

    assert binary_item_id == "image1"
    assert manifest_entry["href"] == "BinData/image1.png"
    assert (work_dir / "BinData" / "image1.png").is_file()


def test_register_image_raises_for_missing_source_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"
    work_dir = tmp_path / "work"

    with pytest.raises(FileNotFoundError, match="이미지 파일"):
        register_image(str(missing), str(work_dir))


def test_register_image_raises_for_unsupported_extension(tmp_path: Path) -> None:
    src = tmp_path / "figure.tiff"
    work_dir = tmp_path / "work"
    _write_fake_image(src, b"fake-tiff")

    with pytest.raises(ValueError, match="지원하지 않는 이미지 확장자"):
        register_image(str(src), str(work_dir))
