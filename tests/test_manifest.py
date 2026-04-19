"""``mapsi.builder.manifest.update_manifest`` 단위 테스트 (Phase 6b)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from lxml import etree

from mapsi.builder.manifest import update_manifest


_OPF = "{http://www.idpf.org/2007/opf/}"
_BASE_HPF = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "base"
    / "unpacked"
    / "Contents"
    / "content.hpf"
)


def _seed(tmp_path: Path) -> Path:
    dest = tmp_path / "content.hpf"
    shutil.copy2(_BASE_HPF, dest)
    return dest


def _items(path: Path) -> list[dict]:
    root = etree.parse(str(path)).getroot()
    manifest = root.find(f"{_OPF}manifest")
    return [
        {
            "id": item.get("id"),
            "href": item.get("href"),
            "media-type": item.get("media-type"),
            "isEmbeded": item.get("isEmbeded"),
        }
        for item in manifest.findall(f"{_OPF}item")
    ]


def test_appends_new_image_item(tmp_path: Path) -> None:
    path = _seed(tmp_path)
    update_manifest(
        path,
        [
            {
                "id": "image1",
                "href": "BinData/image1.png",
                "media-type": "image/png",
            }
        ],
    )
    items = _items(path)
    image_items = [it for it in items if it["id"] == "image1"]
    assert len(image_items) == 1
    assert image_items[0]["href"] == "BinData/image1.png"
    assert image_items[0]["media-type"] == "image/png"
    assert image_items[0]["isEmbeded"] == "1"


def test_preserves_existing_items(tmp_path: Path) -> None:
    path = _seed(tmp_path)
    before_ids = [it["id"] for it in _items(path)]
    update_manifest(
        path,
        [
            {
                "id": "image1",
                "href": "BinData/image1.png",
                "media-type": "image/png",
            }
        ],
    )
    after_ids = [it["id"] for it in _items(path)]
    for sid in before_ids:
        assert sid in after_ids


def test_idempotent_overwrite_existing_id(tmp_path: Path) -> None:
    path = _seed(tmp_path)
    entry = {
        "id": "image1",
        "href": "BinData/image1.png",
        "media-type": "image/png",
    }
    update_manifest(path, [entry])
    update_manifest(
        path,
        [
            {
                "id": "image1",
                "href": "BinData/image1_NEW.png",
                "media-type": "image/jpeg",
            }
        ],
    )
    image_items = [it for it in _items(path) if it["id"] == "image1"]
    assert len(image_items) == 1
    assert image_items[0]["href"] == "BinData/image1_NEW.png"
    assert image_items[0]["media-type"] == "image/jpeg"


def test_multiple_entries_in_one_call(tmp_path: Path) -> None:
    path = _seed(tmp_path)
    update_manifest(
        path,
        [
            {
                "id": "image1",
                "href": "BinData/image1.png",
                "media-type": "image/png",
            },
            {
                "id": "image2",
                "href": "BinData/image2.jpg",
                "media-type": "image/jpeg",
            },
        ],
    )
    ids = {it["id"] for it in _items(path)}
    assert {"image1", "image2"}.issubset(ids)


def test_empty_entries_is_noop(tmp_path: Path) -> None:
    path = _seed(tmp_path)
    before = path.read_bytes()
    update_manifest(path, [])
    assert path.read_bytes() == before


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        update_manifest(tmp_path / "nope.hpf", [{"id": "x", "href": "y", "media-type": "z"}])


def test_missing_required_key_raises(tmp_path: Path) -> None:
    path = _seed(tmp_path)
    with pytest.raises(KeyError):
        update_manifest(path, [{"id": "image1", "href": "BinData/image1.png"}])


def test_xml_declaration_preserved(tmp_path: Path) -> None:
    path = _seed(tmp_path)
    update_manifest(
        path,
        [{"id": "image1", "href": "BinData/image1.png", "media-type": "image/png"}],
    )
    text = path.read_text()
    assert text.startswith("<?xml")
    assert "encoding='UTF-8'" in text or 'encoding="UTF-8"' in text
