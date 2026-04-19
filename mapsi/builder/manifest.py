"""content.hpf manifest 갱신 (계약 4, C 영역).

content.hpf 의 opf:manifest 를 in-place 로 갱신한다.
이미 동일 id 의 항목이 있으면 덮어쓰고, 없으면 추가한다.
opf:spine 은 변경하지 않는다.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree


__all__ = ["update_manifest"]


OPF_NS = "http://www.idpf.org/2007/opf/"
_OPF = f"{{{OPF_NS}}}"


def update_manifest(content_hpf_path: str, entries: list[dict]) -> None:
    """content.hpf 의 opf:manifest 를 in-place 로 갱신한다."""
    if not entries:
        return

    path = Path(content_hpf_path)
    if not path.is_file():
        raise FileNotFoundError(f"content.hpf 파일을 찾을 수 없음: {path}")

    tree = etree.parse(str(path))
    root = tree.getroot()

    manifest = root.find(f"{_OPF}manifest")
    if manifest is None:
        raise ValueError(f"content.hpf 에 opf:manifest 가 없음: {path}")

    existing_items = {
        item.get("id"): item
        for item in manifest.findall(f"{_OPF}item")
        if item.get("id")
    }

    for entry in entries:
        _validate_entry(entry)

        item_id = entry["id"]
        href = entry["href"]
        media_type = entry["media-type"]

        if item_id in existing_items:
            item = existing_items[item_id]
        else:
            item = etree.SubElement(manifest, f"{_OPF}item")
            item.set("id", item_id)
            existing_items[item_id] = item

        item.set("href", href)
        item.set("media-type", media_type)

        if href.startswith("BinData/"):
            item.set("isEmbeded", "1")

    tree.write(
        str(path),
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
        pretty_print=False,
    )


def _validate_entry(entry: dict) -> None:
    required_keys = {"id", "href", "media-type"}
    missing = required_keys - set(entry.keys())
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"manifest entry 에 필수 키가 누락됨: {missing_text}")

    for key in ("id", "href", "media-type"):
        value = entry[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"manifest entry 의 {key!r} 값은 비어 있지 않은 문자열이어야 함"
            )
