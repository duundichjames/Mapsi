"""``mapsi.builder.bindata.register_image`` 단위 테스트 (Phase 6b)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mapsi.builder.bindata import register_image


FIXTURE_PNG = Path(__file__).parent / "fixtures" / "sample_figure.png"


def test_first_call_produces_image1(tmp_path: Path) -> None:
    item_id, entry = register_image(FIXTURE_PNG, tmp_path)
    assert item_id == "image1"
    assert entry == {
        "id": "image1",
        "href": "BinData/image1.png",
        "media-type": "image/png",
    }
    assert (tmp_path / "BinData" / "image1.png").is_file()


def test_subsequent_calls_increment_id(tmp_path: Path) -> None:
    register_image(FIXTURE_PNG, tmp_path)
    item_id, entry = register_image(FIXTURE_PNG, tmp_path)
    assert item_id == "image2"
    assert entry["href"] == "BinData/image2.png"
    assert (tmp_path / "BinData" / "image2.png").is_file()


def test_bindata_dir_auto_created(tmp_path: Path) -> None:
    bindata = tmp_path / "BinData"
    assert not bindata.exists()
    register_image(FIXTURE_PNG, tmp_path)
    assert bindata.is_dir()


def test_existing_bindata_does_not_clobber(tmp_path: Path) -> None:
    """이미 ``image5.png`` 가 존재하면 다음은 ``image6``."""
    (tmp_path / "BinData").mkdir()
    shutil.copy2(FIXTURE_PNG, tmp_path / "BinData" / "image5.png")
    item_id, _ = register_image(FIXTURE_PNG, tmp_path)
    assert item_id == "image6"


def test_non_image_entries_in_bindata_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "BinData").mkdir()
    (tmp_path / "BinData" / "noise.txt").write_text("x")
    item_id, _ = register_image(FIXTURE_PNG, tmp_path)
    assert item_id == "image1"


def test_jpeg_extension_maps_to_image_jpeg(tmp_path: Path) -> None:
    src = tmp_path / "src.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    item_id, entry = register_image(src, tmp_path / "work")
    assert item_id == "image1"
    assert entry["media-type"] == "image/jpeg"
    assert entry["href"] == "BinData/image1.jpg"


def test_missing_src_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        register_image(tmp_path / "nope.png", tmp_path)


def test_no_extension_raises_valueerror(tmp_path: Path) -> None:
    src = tmp_path / "no_ext"
    src.write_bytes(b"x")
    with pytest.raises(ValueError, match="확장자 누락"):
        register_image(src, tmp_path / "work")


def test_unknown_extension_raises_valueerror(tmp_path: Path) -> None:
    src = tmp_path / "foo.xyz"
    src.write_bytes(b"x")
    with pytest.raises(ValueError, match="media type"):
        register_image(src, tmp_path / "work")


def test_extension_lowercased_in_arc_name(tmp_path: Path) -> None:
    src = tmp_path / "src.PNG"
    shutil.copy2(FIXTURE_PNG, src)
    _, entry = register_image(src, tmp_path / "work")
    assert entry["href"] == "BinData/image1.png"
