"""개별 HWPX XML 요소 빌더.

각 함수는 lxml ``Element`` 를 반환한다. ``section.build_section()`` 이 본
모듈의 헬퍼들을 조립해 최종 section0.xml 을 만든다.

요소별 빌더 (현재 구현 / 후속 커밋 예정):
    - build_paragraph: hp:p (문단) -- 구현 완료
    - build_run: hp:run (인라인 서식 그룹) -- 후속
    - build_text_run: hp:run + hp:t (평문) -- 구현 완료 (private 헬퍼)
    - build_table_wrapper: hp:p > hp:run > hp:tbl (표 + 캡션) -- 구현 완료
    - build_picture: hp:pic (그림) -- 후속
    - build_footnote_ref: hp:footnoteRef (각주 참조) -- 후속
"""

from __future__ import annotations

import random
from typing import Any

from lxml import etree

from ..parser import Block
from ..styles import style_name
from .header import StyleEntry


__all__ = [
    "build_paragraph",
    "build_run",
    "build_text_run",
    "build_table_wrapper",
    "build_picture",
    "build_footnote_ref",
]


HWPML_PARA_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HP = f"{{{HWPML_PARA_NS}}}"


# ---------------------------------------------------------------------------
# 표 기본값 상수 — samples/incremental/05_table 의 한/글 출력값 기반.
# 한/글이 표를 열 때 자동 재계산하는 값들이라 큰 정확도는 불필요하지만,
# "한/글이 거부하지 않는" 합리적 기본값을 둔다.
# ---------------------------------------------------------------------------

_TABLE_BORDER_FILL_ID = "6"  # templates/Contents/header.xml 의 표 전용 borderFill
_TABLE_TOTAL_WIDTH = 42537  # HWPUNIT (~본문 폭)
_TABLE_DEFAULT_ROW_HEIGHT = 3030  # HWPUNIT (~ 한 줄)
_TABLE_CELL_SPACING = 0
_TABLE_OUT_MARGIN = (0, 0, 0, 0)  # left, right, top, bottom
_TABLE_IN_MARGIN = (510, 510, 141, 141)
_TABLE_CELL_MARGIN = (510, 510, 141, 141)
_CAPTION_WIDTH = 8504
_CAPTION_GAP = 850


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


def build_table_wrapper(
    block: Block,
    style_map: dict[str, Any],
    style_table: dict[str, StyleEntry],
) -> etree._Element:
    """표 1 개를 담는 wrapper ``hp:p`` 노드를 생성한다.

    HWPX 의 표는 단독 노드가 아니라 wrapper paragraph 의 ``hp:run`` 안에
    ``hp:tbl`` 형태로 들어간다. 이 함수가 그 wrapper 와 내부 구조 전부를
    조립한다.

    구조 개요::

        <hp:p paraPrIDRef styleIDRef>          ← 본문 스타일 wrapper
          <hp:run charPrIDRef>
            <hp:tbl rowCnt colCnt borderFillIDRef ...>
              <hp:sz/> <hp:pos/> <hp:outMargin/>
              [<hp:caption><hp:subList><hp:p 표캡션>...</hp:p></hp:subList></hp:caption>]
              <hp:inMargin/>
              <hp:tr>
                <hp:tc borderFillIDRef>
                  <hp:subList>
                    <hp:p 표내용>
                      <hp:run><hp:t>cell text</hp:t></hp:run>
                    </hp:p>
                  </hp:subList>
                  <hp:cellAddr/> <hp:cellSpan/> <hp:cellSz/> <hp:cellMargin/>
                </hp:tc>
                ...
              </hp:tr>
              ...
            </hp:tbl>
          </hp:run>
        </hp:p>

    Parameters
    ----------
    block:
        ``role="table"`` Block. ``meta["rows"]`` 는 ``list[list[str]]``,
        ``meta["caption"]`` 은 ``str | None``.
    style_map / style_table:
        :func:`build_paragraph` 와 동일.

    Notes
    -----
    표 ID 는 한/글이 문서 내 유일성을 요구하므로 32-bit 양의 정수를 무작위로
    부여한다. 동일 입력에 대해 결정적으로 만들고 싶다면 향후 시드 주입
    인터페이스를 도입.
    """
    rows = block.meta.get("rows") or []
    caption = block.meta.get("caption")
    row_count = len(rows)
    col_count = max((len(r) for r in rows), default=0)
    if row_count == 0 or col_count == 0:
        raise ValueError("table block 에 rows 가 없거나 비어있음")

    body_entry = style_table[style_name(style_map, "paragraph", 0)]
    cell_entry = style_table[style_name(style_map, "table_cell", 0)]
    caption_entry = (
        style_table[style_name(style_map, "table_caption", 0)] if caption else None
    )

    wrapper = etree.Element(
        f"{_HP}p",
        attrib={
            "id": "0",
            "paraPrIDRef": body_entry.para_pr_id,
            "styleIDRef": body_entry.id,
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0",
        },
    )
    run = etree.SubElement(
        wrapper, f"{_HP}run", attrib={"charPrIDRef": body_entry.char_pr_id}
    )

    table_height = _TABLE_DEFAULT_ROW_HEIGHT * row_count
    cell_width = _TABLE_TOTAL_WIDTH // col_count

    tbl = etree.SubElement(
        run,
        f"{_HP}tbl",
        attrib={
            "id": str(random.randint(1, 2**31 - 1)),
            "zOrder": "0",
            "numberingType": "TABLE",
            "textWrap": "TOP_AND_BOTTOM",
            "textFlow": "BOTH_SIDES",
            "lock": "0",
            "dropcapstyle": "None",
            "pageBreak": "TABLE",
            "repeatHeader": "1",
            "rowCnt": str(row_count),
            "colCnt": str(col_count),
            "cellSpacing": str(_TABLE_CELL_SPACING),
            "borderFillIDRef": _TABLE_BORDER_FILL_ID,
            "noAdjust": "0",
        },
    )
    etree.SubElement(
        tbl,
        f"{_HP}sz",
        attrib={
            "width": str(_TABLE_TOTAL_WIDTH),
            "widthRelTo": "ABSOLUTE",
            "height": str(table_height),
            "heightRelTo": "ABSOLUTE",
            "protect": "0",
        },
    )
    etree.SubElement(
        tbl,
        f"{_HP}pos",
        attrib={
            "treatAsChar": "0",
            "affectLSpacing": "0",
            "flowWithText": "1",
            "allowOverlap": "0",
            "holdAnchorAndSO": "0",
            "vertRelTo": "PARA",
            "horzRelTo": "PARA",
            "vertAlign": "TOP",
            "horzAlign": "LEFT",
            "vertOffset": "0",
            "horzOffset": "0",
        },
    )
    etree.SubElement(
        tbl,
        f"{_HP}outMargin",
        attrib=_margin_attrs(_TABLE_OUT_MARGIN),
    )
    if caption_entry is not None:
        tbl.append(_build_caption(str(caption), caption_entry))
    etree.SubElement(
        tbl,
        f"{_HP}inMargin",
        attrib=_margin_attrs(_TABLE_IN_MARGIN),
    )

    for row_idx, row in enumerate(rows):
        tr = etree.SubElement(tbl, f"{_HP}tr")
        for col_idx in range(col_count):
            text = row[col_idx] if col_idx < len(row) else ""
            tr.append(
                _build_cell(
                    text=text,
                    col=col_idx,
                    row=row_idx,
                    cell_width=cell_width,
                    cell_entry=cell_entry,
                )
            )
    return wrapper


def _build_caption(text: str, caption_entry: StyleEntry) -> etree._Element:
    """``<hp:caption>`` 노드를 만든다. 표 1 개당 최대 1 개.

    한/글의 표 캡션은 캡션 본문 앞에 자동 번호 마커 (``<hp:autoNum>``) 를
    삽입하여 "표 1 본문" / "표 2 본문" 처럼 표시한다. 본 함수는
    `<hp:t>표 </hp:t><hp:ctrl><hp:autoNum/></hp:ctrl><hp:t> 본문</hp:t>` 의
    표준 패턴을 emit. 한/글이 문서 오픈 시 ``num`` 속성을 재계산한다.
    """
    caption = etree.Element(
        f"{_HP}caption",
        attrib={
            "side": "TOP",
            "fullSz": "0",
            "width": str(_CAPTION_WIDTH),
            "gap": str(_CAPTION_GAP),
            "lastWidth": str(_TABLE_TOTAL_WIDTH),
        },
    )
    sublist = etree.SubElement(
        caption,
        f"{_HP}subList",
        attrib=_sublist_attrs(vert_align="TOP"),
    )
    p = etree.SubElement(
        sublist,
        f"{_HP}p",
        attrib={
            "id": "0",
            "paraPrIDRef": caption_entry.para_pr_id,
            "styleIDRef": caption_entry.id,
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0",
        },
    )
    run = etree.SubElement(
        p, f"{_HP}run", attrib={"charPrIDRef": caption_entry.char_pr_id}
    )
    prefix_t = etree.SubElement(run, f"{_HP}t")
    prefix_t.text = "표 "
    ctrl = etree.SubElement(run, f"{_HP}ctrl")
    auto_num = etree.SubElement(
        ctrl,
        f"{_HP}autoNum",
        attrib={"num": "1", "numType": "TABLE"},
    )
    etree.SubElement(
        auto_num,
        f"{_HP}autoNumFormat",
        attrib={
            "type": "DIGIT",
            "userChar": "",
            "prefixChar": "",
            "suffixChar": "",
            "supscript": "0",
        },
    )
    body_t = etree.SubElement(run, f"{_HP}t")
    body_t.text = " " + text
    return caption


def _build_cell(
    text: str,
    col: int,
    row: int,
    cell_width: int,
    cell_entry: StyleEntry,
) -> etree._Element:
    """``<hp:tc>`` 셀 노드 1 개를 만든다."""
    tc = etree.Element(
        f"{_HP}tc",
        attrib={
            "name": "",
            "header": "0",
            "hasMargin": "0",
            "protect": "0",
            "editable": "0",
            "dirty": "0",
            "borderFillIDRef": _TABLE_BORDER_FILL_ID,
        },
    )
    sublist = etree.SubElement(
        tc,
        f"{_HP}subList",
        attrib=_sublist_attrs(vert_align="CENTER"),
    )
    p = etree.SubElement(
        sublist,
        f"{_HP}p",
        attrib={
            "id": "0",
            "paraPrIDRef": cell_entry.para_pr_id,
            "styleIDRef": cell_entry.id,
            "pageBreak": "0",
            "columnBreak": "0",
            "merged": "0",
        },
    )
    p.append(_make_text_run(text, cell_entry.char_pr_id))
    etree.SubElement(
        tc,
        f"{_HP}cellAddr",
        attrib={"colAddr": str(col), "rowAddr": str(row)},
    )
    etree.SubElement(
        tc,
        f"{_HP}cellSpan",
        attrib={"colSpan": "1", "rowSpan": "1"},
    )
    etree.SubElement(
        tc,
        f"{_HP}cellSz",
        attrib={"width": str(cell_width), "height": str(_TABLE_DEFAULT_ROW_HEIGHT)},
    )
    etree.SubElement(
        tc,
        f"{_HP}cellMargin",
        attrib=_margin_attrs(_TABLE_CELL_MARGIN),
    )
    return tc


def _margin_attrs(margins: tuple[int, int, int, int]) -> dict[str, str]:
    """(left, right, top, bottom) 튜플을 속성 dict 로 변환."""
    left, right, top, bottom = margins
    return {
        "left": str(left),
        "right": str(right),
        "top": str(top),
        "bottom": str(bottom),
    }


def _sublist_attrs(vert_align: str) -> dict[str, str]:
    """``<hp:subList>`` 공통 속성. 캡션과 셀에서 ``vertAlign`` 만 다름."""
    return {
        "id": "",
        "textDirection": "HORIZONTAL",
        "lineWrap": "BREAK",
        "vertAlign": vert_align,
        "linkListIDRef": "0",
        "linkListNextIDRef": "0",
        "textWidth": "0",
        "textHeight": "0",
        "hasTextRef": "0",
        "hasNumRef": "0",
    }


def build_picture(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """그림(hp:pic) 노드를 생성한다 (후속 픽스처에서 구현)."""
    raise NotImplementedError


def build_footnote_ref(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """각주 참조(hp:footnoteRef) 노드를 생성한다 (후속 픽스처에서 구현)."""
    raise NotImplementedError
