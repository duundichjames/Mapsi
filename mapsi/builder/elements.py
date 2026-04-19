"""개별 HWPX XML 요소 빌더.

각 함수는 lxml ``Element`` 를 반환한다. ``section.build_section()`` 이 본
모듈의 헬퍼들을 조립해 최종 section0.xml 을 만든다.

요소별 빌더 (현재 구현 / 후속 커밋 예정):
    - build_paragraph: hp:p (문단) -- 구현 완료
    - build_run: hp:run (인라인 서식 그룹) -- 후속
    - build_text_run: hp:run + hp:t (평문) -- 구현 완료 (private 헬퍼)
    - build_table: hp:tbl (표) -- 후속
    - build_picture: hp:pic (그림) -- 후속
    - build_footnote_ref: hp:footnoteRef (각주 참조) -- 후속
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from ..parser import Block
from ..styles import style_name
from .header import StyleEntry


__all__ = [
    "build_paragraph",
    "build_run",
    "build_text_run",
    "build_table",
    "build_picture",
    "build_footnote_ref",
]


HWPML_PARA_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HP = f"{{{HWPML_PARA_NS}}}"


def build_paragraph(
    block: Block,
    style_map: dict[str, Any],
    style_table: dict[str, StyleEntry],
) -> etree._Element:
    """문단(``hp:p``) 노드를 생성한다.

    Parameters
    ----------
    block:
        파서 + walker 통과한 Block. ``role`` 과 ``depth`` 로 스타일 결정.
    style_map:
        ``config.load_style_map()`` 의 반환값. role/depth → 스타일 *이름* 룩업.
    style_table:
        ``builder.header.parse_style_table()`` 의 반환값.
        스타일 이름 → ``StyleEntry`` (id, paraPrIDRef, charPrIDRef) 룩업.

    Returns
    -------
    lxml Element
        ``hp:p`` 노드. 자식으로 ``hp:run`` 1 개를 가지며, 그 안에
        텍스트가 있으면 ``hp:t`` 한 노드를 가진다. ``hp:linesegarray``
        는 한/글이 문서 오픈 시 자동 생성하므로 우리는 출력하지 않는다.

    Raises
    ------
    StyleLookupError
        ``style_map`` 에 해당 role/depth 가 없을 때 (= styles.yaml 미정의).
    KeyError
        ``style_table`` 에 해당 이름이 없을 때 (= header.xml 미정의).
    """
    name = style_name(style_map, block.role, block.depth)
    if name not in style_table:
        raise KeyError(
            f"스타일 이름 {name!r} (role={block.role!r}, depth={block.depth}) "
            f"이 header.xml 에 정의돼 있지 않다"
        )
    entry = style_table[name]

    p = etree.Element(
        f"{_HP}p",
        attrib={
            "id": "0",
            "paraPrIDRef": entry.para_pr_id,
            "styleIDRef": entry.id,
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0",
        },
    )
    p.append(_make_text_run(block.text, entry.char_pr_id))
    return p


def _make_text_run(text: str, char_pr_id: str) -> etree._Element:
    """텍스트 1 개를 담는 ``hp:run`` 노드를 만든다.

    텍스트가 빈 문자열이면 ``hp:run`` 만 만들고 ``hp:t`` 는 추가하지 않는다.
    """
    run = etree.Element(f"{_HP}run", attrib={"charPrIDRef": char_pr_id})
    if text:
        t = etree.SubElement(run, f"{_HP}t")
        t.text = text
    return run


def build_run(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """인라인 런(hp:run) 노드를 생성한다 (후속 픽스처에서 구현)."""
    raise NotImplementedError


def build_text_run(text: str, char_pr_id: str = "0") -> etree._Element:
    """평문 런(hp:run + hp:t) 을 생성한다.

    ``build_paragraph`` 가 내부 헬퍼 ``_make_text_run`` 을 쓰지만,
    독립 호출이 필요한 경우 (표 셀 내부 등) 를 위해 공개 래퍼.
    """
    return _make_text_run(text, char_pr_id)


def build_table(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """표(hp:tbl) 노드를 생성한다 (후속 픽스처에서 구현)."""
    raise NotImplementedError


def build_picture(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """그림(hp:pic) 노드를 생성한다 (후속 픽스처에서 구현)."""
    raise NotImplementedError


def build_footnote_ref(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """각주 참조(hp:footnoteRef) 노드를 생성한다 (후속 픽스처에서 구현)."""
    raise NotImplementedError
