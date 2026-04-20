"""mapsi.builder.manifest 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from mapsi.builder.manifest import update_manifest


OPF_NS = "http://www.idpf.org/2007/opf/"
NS = {"opf": OPF_NS}


def _copy_base_content_hpf(samples_dir: Path, tmp_path: Path) -> Path:
    src = samples_dir / "base" / "unpacked" / "Contents" / "content.hpf"
    dst = tmp_path / "content.hpf"
    dst.write_bytes(src.read_bytes())
    return dst


def _parse_manifest(path: Path):
    tree = etree.parse(str(path))
    root = tree.getroot()
    manifest = root.find("opf:manifest", namespaces=NS)
    assert manifest is not None
    return tree, root, manifest


def test_update_manifest_noop_when_entries_empty(samples_dir: Path, tmp_path: Path) -> None:
    content_hpf = _copy_base_content_hpf(samples_dir, tmp_path)
    before = content_hpf.read_bytes()

    update_manifest(str(content_hpf), [])

    after = content_hpf.read_bytes()
    assert after == before


def test_update_manifest_adds_new_item(samples_dir: Path, tmp_path: Path) -> None:
    content_hpf = _copy_base_content_hpf(samples_dir, tmp_path)

    update_manifest(
        str(content_hpf),
        [
            {
                "id": "image1",
                "href": "BinData/image1.png",
                "media-type": "image/png",
            }
        ],
    )

    _, _, manifest = _parse_manifest(content_hpf)
    item = manifest.find("opf:item[@id='image1']", namespaces=NS)

    assert item is not None
    assert item.get("href") == "BinData/image1.png"
    assert item.get("media-type") == "image/png"
    assert item.get("isEmbeded") == "1"


def test_update_manifest_overwrites_existing_item(samples_dir: Path, tmp_path: Path) -> None:
    content_hpf = _copy_base_content_hpf(samples_dir, tmp_path)

    update_manifest(
        str(content_hpf),
        [
            {
                "id": "image1",
                "href": "BinData/image1.png",
                "media-type": "image/png",
            }
        ],
    )

    update_manifest(
        str(content_hpf),
        [
            {
                "id": "image1",
                "href": "BinData/image1.jpg",
                "media-type": "image/jpeg",
            }
        ],
    )

    _, _, manifest = _parse_manifest(content_hpf)
    items = manifest.findall("opf:item[@id='image1']", namespaces=NS)

    assert len(items) == 1
    assert items[0].get("href") == "BinData/image1.jpg"
    assert items[0].get("media-type") == "image/jpeg"
    assert items[0].get("isEmbeded") == "1"


def test_update_manifest_keeps_spine_unchanged(samples_dir: Path, tmp_path: Path) -> None:
    content_hpf = _copy_base_content_hpf(samples_dir, tmp_path)

    tree_before = etree.parse(str(content_hpf))
    spine_before = etree.tostring(
        tree_before.getroot().find("opf:spine", namespaces=NS)
    )

    update_manifest(
        str(content_hpf),
        [
            {
                "id": "image1",
                "href": "BinData/image1.bmp",
                "media-type": "image/bmp",
            }
        ],
    )

    tree_after = etree.parse(str(content_hpf))
    spine_after = etree.tostring(
        tree_after.getroot().find("opf:spine", namespaces=NS)
    )

    assert spine_after == spine_before


def test_update_manifest_raises_when_required_key_missing(
    samples_dir: Path,
    tmp_path: Path,
) -> None:
    content_hpf = _copy_base_content_hpf(samples_dir, tmp_path)

    with pytest.raises(ValueError, match="필수 키"):
        update_manifest(
            str(content_hpf),
            [
                {
                    "id": "image1",
                    "href": "BinData/image1.png",
                }
            ],
        )


def test_update_manifest_raises_when_value_is_blank(
    samples_dir: Path,
    tmp_path: Path,
) -> None:
    content_hpf = _copy_base_content_hpf(samples_dir, tmp_path)

    with pytest.raises(ValueError, match="비어 있지 않은 문자열"):
        update_manifest(
            str(content_hpf),
            [
                {
                    "id": "image1",
                    "href": "",
                    "media-type": "image/png",
                }
            ],
        )


def test_update_manifest_raises_when_manifest_is_missing(tmp_path: Path) -> None:
    broken = tmp_path / "broken.hpf"
    broken.write_text(
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<opf:package xmlns:opf="http://www.idpf.org/2007/opf/">
  <opf:metadata />
  <opf:spine />
</opf:package>
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="opf:manifest"):
        update_manifest(
            str(broken),
            [
                {
                    "id": "image1",
                    "href": "BinData/image1.png",
                    "media-type": "image/png",
                }
            ],
        )
