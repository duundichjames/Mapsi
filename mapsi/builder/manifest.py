"""``content.hpf`` 의 ``opf:manifest`` 패치 (계약 4, C 영역).

C 부재 기간 동안 B 가 임시 구현. 그림이 등장한 문서를 변환할 때
``register_image`` 가 발급한 manifest 항목들을 모아서 한 번에 호출하여
``content.hpf`` 에 in-place 로 기록한다.

계약 표면 (``spec/interfaces.md`` §계약 4):

.. code-block:: python

    def update_manifest(content_hpf_path: str, entries: list[dict]) -> None:
        ...

각 entry dict 는 ``id``, ``href``, ``media-type`` 키를 갖는다 (계약 3 의
``register_image`` 가 정확히 이 형태로 반환). 본 함수는 추가로
``isEmbeded="1"`` 속성을 모든 항목에 부여한다 — 한/글이 BinData 의
바이너리를 문서 내부 자산으로 인식하기 위해 필요하며, 우리 변환기는 외부
링크 그림을 발급하지 않으므로 항상 1.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree


__all__ = ["update_manifest"]


_OPF_NS = "http://www.idpf.org/2007/opf/"
_OPF = f"{{{_OPF_NS}}}"


def update_manifest(
    content_hpf_path: str | Path,
    entries: list[dict],
) -> None:
    """``content.hpf`` 의 ``opf:manifest`` 를 in-place 로 갱신한다.

    Parameters
    ----------
    content_hpf_path:
        대상 ``content.hpf`` 파일 경로.
    entries:
        추가/갱신할 항목 리스트. 각 항목은 dict 이며 키는 ``id``,
        ``href``, ``media-type`` (계약 3 의 ``register_image`` 반환 형태).
        동일 ``id`` 가 manifest 에 이미 있으면 덮어쓴다 (멱등).

    Side effects
    ------------
    - 파일을 읽어 XML 파싱 → manifest 갱신 → 파일에 다시 기록.
    - 파일 외 다른 부분 (metadata, spine 등) 은 변경하지 않는다.

    Raises
    ------
    FileNotFoundError
        대상 파일이 없을 때.
    KeyError
        entry 에 필수 키 (``id``, ``href``, ``media-type``) 가 빠졌을 때.
    """
    path = Path(content_hpf_path)
    if not path.is_file():
        raise FileNotFoundError(f"content.hpf 가 없음: {path}")
    if not entries:
        return

    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    manifest = root.find(f"{_OPF}manifest")
    if manifest is None:
        raise ValueError(
            f"content.hpf 에 <opf:manifest> 가 없음: {path}"
        )

    by_id: dict[str, etree._Element] = {}
    for item in manifest.findall(f"{_OPF}item"):
        item_id = item.get("id")
        if item_id is not None:
            by_id[item_id] = item

    for entry in entries:
        item_id = entry["id"]
        href = entry["href"]
        media_type = entry["media-type"]
        existing = by_id.get(item_id)
        if existing is not None:
            existing.set("href", href)
            existing.set("media-type", media_type)
            existing.set("isEmbeded", "1")
        else:
            new_item = etree.SubElement(
                manifest,
                f"{_OPF}item",
                attrib={
                    "id": item_id,
                    "href": href,
                    "media-type": media_type,
                    "isEmbeded": "1",
                },
            )
            by_id[item_id] = new_item

    path.write_bytes(
        etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
    )
