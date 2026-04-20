"""개별 HWPX XML 요소 빌더.

각 함수는 lxml ``Element`` 를 반환한다. ``section.build_section()`` 이 본
모듈의 헬퍼들을 조립해 최종 section0.xml 을 만든다.

요소별 빌더 (현재 구현 / 후속 커밋 예정):
    - build_paragraph: hp:p (문단; footnote_marks 가 있으면 hp:run 안에
      hp:t / hp:ctrl(footNote) 를 번갈아 emit) -- 구현 완료
    - build_run: hp:run (인라인 서식 그룹) -- 후속
    - build_text_run: hp:run + hp:t (평문) -- 구현 완료 (private 헬퍼)
    - build_table_wrapper: hp:p > hp:run > hp:tbl (표 + 캡션) -- 구현 완료
    - build_figure_paragraph: hp:p (이미지 ID 가 있으면 hp:pic 포함) -- Phase 6b
    - build_figure_caption_paragraph: hp:p (그림캡션 + autoNum) -- 사용 안 함
      (Phase 6a 의 자리표시였으며 6b 에서 캡션은 hp:pic 내부로 이동.
      외부 테스트 호환을 위해 함수 자체는 보존)
    - build_picture: hp:pic 노드 (private 헬퍼 _build_pic 가 본체) -- Phase 6b
    - build_footnote_ref: 미사용 (Phase 7 에서 _build_footnote 로 통합)

각주 emit 방식 (Phase 7)
------------------------

paragraph Block 의 ``meta["footnote_marks"]`` 가 있으면 ``build_paragraph``
는 다음과 같이 emit 한다 (한/글 본가 출력과 동일 구조)::

    <hp:p ...>
      <hp:run charPrIDRef="...">
        <hp:t>마커 직전 평문</hp:t>
        <hp:ctrl>
          <hp:footNote number="N" suffixChar="41" instId="...">
            <hp:subList ...>
              <hp:p styleIDRef="각주">
                <hp:run>
                  <hp:ctrl><hp:autoNum num="N" numType="FOOTNOTE"/></hp:ctrl>
                  <hp:t> 각주 본문</hp:t>
                </hp:run>
              </hp:p>
            </hp:subList>
          </hp:footNote>
        </hp:ctrl>
        <hp:t>마커 직후 평문</hp:t>
      </hp:run>
    </hp:p>

번호 ``N`` 은 ``mark["footnote_id"] + 1`` (0-base → 1-base). 한/글이 자동
재계산하지만 명시적 값을 두면 호환성이 좋다. 본문 텍스트 앞 공백 1개는
한/글 출력 관습 (자동번호와 본문 분리). 각주 본문 단락의 스타일은
``styles.yaml`` 의 ``footnote`` 매핑 (= "각주") 을 동적으로 룩업.

그림 emit 방식 (Phase 6b)
-------------------------

``build_figure_paragraph`` 는 ``image_info`` 인자를 받는다.

- ``image_info=None`` → Phase 6a 호환 모드. 이미지 없는 ``그림`` 스타일
  자리표시 단락 (alt 텍스트만 보존). 실 임베드 전환 전 단위 테스트
  호환용.
- ``image_info`` dict (``{"binary_item_id", "width_hwpunit",
  "height_hwpunit"}``) → ``hp:run`` 안에 ``hp:pic`` 을 끼워 emit.
  ``block.meta["caption"]`` 이 있으면 ``hp:pic`` 내부 ``hp:caption`` 으로
  흡수 (표와 동일한 모델, ``numType="PICTURE"``).

호출자 (``section.build_section`` 또는 ``converter.md_to_hwpx``) 가 미리
``register_image`` 로 ID 를 발급하고 ``Pillow`` 로 픽셀 크기를 측정해
HWPUNIT 으로 환산한 뒤 ``image_info`` 를 구성한다.
"""

from __future__ import annotations

import random
from typing import Any

from lxml import etree

from ..inline_styles import HYPERLINK_CHARPR_ID, resolve_charpr
from ..parser import Block
from ..styles import style_name
from .header import StyleEntry


__all__ = [
    "build_paragraph",
    "build_run",
    "build_text_run",
    "build_table_wrapper",
    "build_figure_paragraph",
    "build_figure_caption_paragraph",
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
        ``meta["footnote_marks"]`` 가 있으면 인라인 각주를 끼워 emit.
        ``meta["equation_marks"]`` 가 있으면 인라인/디스플레이 수식 마커를
        끼워 emit (ADR 0002).
    style_map:
        ``config.load_style_map()`` 의 반환값. role/depth → 스타일 *이름* 룩업.
        각주 본문 단락 스타일 (= ``footnote`` → ``"각주"``) 룩업에도 사용.
    style_table:
        ``builder.header.parse_style_table()`` 의 반환값.
        스타일 이름 → ``StyleEntry`` (id, paraPrIDRef, charPrIDRef) 룩업.

    Returns
    -------
    lxml Element
        ``hp:p`` 노드. 평문이면 ``hp:run`` 1 개 (안에 ``hp:t`` 1 개) 를
        가진다. 각주 마크가 있으면 ``hp:run`` 1 개 안에 ``hp:t`` 와
        ``hp:ctrl(hp:footNote)`` 가 마커 위치에 따라 번갈아 등장한다.
        ``hp:linesegarray`` 는 한/글이 문서 오픈 시 자동 생성하므로 우리는
        출력하지 않는다.

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
    meta = block.meta or {}
    foot_marks = meta.get("footnote_marks")
    eq_marks = meta.get("equation_marks")
    inline_marks = meta.get("inline_marks")
    if sum(bool(x) for x in (foot_marks, eq_marks, inline_marks)) > 1:
        raise NotImplementedError(
            "한 단락에 각주/수식/인라인 서식이 둘 이상 동시에 있는 경우는 "
            "v0.1 에서 지원하지 않는다 (ADR 0004 영향 절 참조; 통합은 v0.2)"
        )
    if foot_marks:
        p.append(
            _make_run_with_footnotes(
                block.text, foot_marks, entry.char_pr_id, style_map, style_table
            )
        )
    elif eq_marks:
        p.append(
            _make_run_with_equations(block.text, eq_marks, entry.char_pr_id)
        )
    elif inline_marks:
        for run in _make_runs_with_inline_marks(
            block.text, inline_marks, entry.char_pr_id
        ):
            p.append(run)
    else:
        p.append(_make_text_run(block.text, entry.char_pr_id))
    return p


def _make_runs_with_inline_marks(
    text: str,
    marks: list[dict[str, Any]],
    base_char_pr_id: str,
) -> list[etree._Element]:
    """인라인 서식 마크가 있는 단락을 ``hp:run`` 여러 개로 emit (Phase 10).

    각 ``hp:run`` 의 ``charPrIDRef`` 는 그 자리에서 활성화된 마크 집합을
    ``mapsi.inline_styles.resolve_charpr`` 로 룩업해 결정한다. 마크가
    하나도 없는 세그먼트는 ``base_char_pr_id`` (= 단락 스타일이 가리키는
    본문 charPr) 를 사용한다.

    알고리즘
    --------
    1. 모든 마크의 ``start`` / ``end`` 와 ``0`` / ``len(text)`` 를 모아
       경계 (boundary) 집합을 만든다.
    2. 정렬·중복제거한 경계로 ``text`` 를 세그먼트로 자른다.
    3. 각 세그먼트에서 활성 마크 집합 = ``{m.kind | m.start ≤ seg.start
       and seg.end ≤ m.end}``. 링크는 URL 도 함께 기억한다.
    4. 활성 집합에 ``link`` 가 있으면 charPr 를
       :data:`mapsi.inline_styles.HYPERLINK_CHARPR_ID` (= 파란 + 밑줄)
       로 고정하고, 해당 세그먼트는 ``hp:fieldBegin/fieldEnd`` 3-run
       쌍으로 emit (ADR 0004 결정 1 v0.1.1). 링크 세그먼트는 인접
       merge 대상이 아니다 (각 필드가 독립 ID 를 가져야 한다).
    5. ``link`` 가 없는 세그먼트는 기존 룩업 → charPr. 비활성 (집합
       비었음) 은 ``base_char_pr_id`` 를 직접 사용.
    6. 인접 non-link 세그먼트의 charPr 가 같으면 합쳐서 출력 단순화.
    7. 빈 세그먼트는 emit 하지 않는다.

    HYPERLINK 3-run 구조 (python-hwpx `add_hyperlink` 참고)::

        <hp:run charPrIDRef="30">
          <hp:ctrl>
            <hp:fieldBegin id="<uuid>" type="HYPERLINK" name="<URL>"
                           editable="false" dirty="false"/>
          </hp:ctrl>
        </hp:run>
        <hp:run charPrIDRef="30"><hp:t>라벨</hp:t></hp:run>
        <hp:run charPrIDRef="30">
          <hp:ctrl><hp:fieldEnd beginIDRef="<uuid>"/></hp:ctrl>
        </hp:run>

    Returns
    -------
    list[lxml Element]
        ``<hp:run>`` 노드들의 리스트.

    Notes
    -----
    각주/수식과 동시 등장은 호출자 (``build_paragraph``) 가 거부한다.
    링크가 bold 등 다른 시각 마크와 겹치면 링크 charPr 가 이긴다
    (클릭 가능성 보존이 조합 시각 서식보다 우선).
    """
    boundaries = {0, len(text)}
    for m in marks:
        boundaries.add(int(m["start"]))
        boundaries.add(int(m["end"]))
    sorted_bounds = sorted(b for b in boundaries if 0 <= b <= len(text))

    runs: list[etree._Element] = []
    last_char_pr: str | None = None
    last_run: etree._Element | None = None
    last_t: etree._Element | None = None

    for lo, hi in zip(sorted_bounds, sorted_bounds[1:]):
        if lo >= hi:
            continue
        active_marks = [
            m for m in marks
            if int(m["start"]) <= lo and hi <= int(m["end"])
        ]
        active_kinds = {m["kind"] for m in active_marks}
        seg_text = text[lo:hi]

        link_mark = next(
            (m for m in active_marks if m["kind"] == "link" and m.get("url")),
            None,
        )
        if link_mark is not None:
            url = str(link_mark["url"])
            runs.extend(_make_hyperlink_runs(seg_text, url))
            last_char_pr = None
            last_run = None
            last_t = None
            continue

        char_pr = (
            resolve_charpr(active_kinds) if active_kinds else base_char_pr_id
        )
        if last_run is not None and char_pr == last_char_pr and last_t is not None:
            last_t.text = (last_t.text or "") + seg_text
            continue
        run = etree.Element(f"{_HP}run", attrib={"charPrIDRef": char_pr})
        t = etree.SubElement(run, f"{_HP}t")
        t.text = seg_text
        runs.append(run)
        last_char_pr = char_pr
        last_run = run
        last_t = t
    return runs


def _make_hyperlink_runs(label: str, url: str) -> list[etree._Element]:
    """HYPERLINK 필드로 감싼 3-run (fieldBegin / text / fieldEnd) 을 만든다.

    한/글이 *실제로 클릭을 활성화* 하려면 ``hp:fieldBegin[@name]`` 에 URL 을
    넣는 축약형 (python-hwpx ``add_hyperlink``) 으로는 부족하고, 한/글이
    export 하는 "정식" 파라미터 블록이 필요하다. 본 함수는 한/글이 직접
    저장한 ``python-hwpx`` fixture (``shared/hwpx/fixtures/fields/
    10_fieldcodes_min.hwpx``) 에서 추출한 다음 형태를 emit 한다 (v0.1.2)::

        <hp:run charPrIDRef="30">
          <hp:ctrl>
            <hp:fieldBegin id="<A>" type="HYPERLINK" name=""
                           editable="0" dirty="1"
                           zorder="-1" fieldid="<B>" metaTag="">
              <hp:parameters cnt="7" name="">
                <hp:integerParam name="Prop">0</hp:integerParam>
                <hp:stringParam name="Command"><ESCAPED_URL>|<TT>;1;0;0;</hp:stringParam>
                <hp:stringParam name="Path"><URL></hp:stringParam>
                <hp:stringParam name="Category"><HWPHYPERLINK_TYPE_*></hp:stringParam>
                <hp:stringParam name="TargetType">HWPHYPERLINK_TARGET_BOOKMARK</hp:stringParam>
                <hp:stringParam name="DocOpenType">HWPHYPERLINK_JUMP_CURRENTTAB</hp:stringParam>
                <hp:stringParam name="ToolTip"><TT></hp:stringParam>
              </hp:parameters>
            </hp:fieldBegin>
          </hp:ctrl>
        </hp:run>
        <hp:run charPrIDRef="30"><hp:t>라벨</hp:t></hp:run>
        <hp:run charPrIDRef="30">
          <hp:ctrl><hp:fieldEnd beginIDRef="<A>" fieldid="<B>"/></hp:ctrl>
          <hp:t/>
        </hp:run>

    ``id`` 와 ``fieldid`` 는 각각 *독립* 난수이지만, ``fieldEnd`` 의
    ``beginIDRef`` 는 반드시 ``fieldBegin/@id`` 와 같고, ``fieldEnd/@fieldid``
    는 ``fieldBegin/@fieldid`` 와 같다 (한/글이 쌍을 ID 둘 모두로 매칭).

    Category 규칙 (URL 모양으로 결정):

    - ``#...`` (앵커) → ``HWPHYPERLINK_TYPE_BOOKMARK``
    - 그 외 (``http``, ``https``, ``mailto``, 상대/절대 경로) →
      ``HWPHYPERLINK_TYPE_URL``

    Command 문자열의 ``:`` 는 한/글 규약상 ``\\:`` 로 escape 한다 (구분자와
    충돌 방지). ``|`` 는 파라미터 구분자이므로 URL 에 실제로 들어 있으면
    ``\\|`` 로 escape 한다. ``Path`` 에는 escape 하지 않은 원 URL 을 그대로
    둔다 (한/글이 실제 열기에 사용하는 값).

    Parameters
    ----------
    label : str
        화면에 보일 텍스트 (빈 문자열이면 URL 자체를 표시).
    url : str
        필드에 박을 하이퍼링크 타깃.

    Returns
    -------
    list[lxml Element]
        3 개의 ``hp:run`` (fieldBegin / text / fieldEnd).
    """
    field_id = str(random.randint(1, 2**31 - 1))
    inst_id = str(random.randint(1, 2**31 - 1))
    cp = HYPERLINK_CHARPR_ID
    display = label if label else url
    tooltip = display
    category = (
        "HWPHYPERLINK_TYPE_BOOKMARK" if url.startswith("#")
        else "HWPHYPERLINK_TYPE_URL"
    )
    escaped_url = url.replace("\\", "\\\\").replace(":", r"\:").replace("|", r"\|")
    escaped_tooltip = tooltip.replace(";", r"\;")
    command_value = f"{escaped_url}|{escaped_tooltip};1;0;0;"

    begin_run = etree.Element(f"{_HP}run", attrib={"charPrIDRef": cp})
    ctrl_begin = etree.SubElement(begin_run, f"{_HP}ctrl")
    field_begin = etree.SubElement(
        ctrl_begin,
        f"{_HP}fieldBegin",
        attrib={
            "id": field_id,
            "type": "HYPERLINK",
            "name": "",
            "editable": "0",
            "dirty": "1",
            "zorder": "-1",
            "fieldid": inst_id,
            "metaTag": "",
        },
    )
    params = etree.SubElement(
        field_begin,
        f"{_HP}parameters",
        attrib={"cnt": "7", "name": ""},
    )

    def _int_param(name: str, value: str) -> None:
        node = etree.SubElement(
            params, f"{_HP}integerParam", attrib={"name": name}
        )
        node.text = value

    def _str_param(name: str, value: str) -> None:
        node = etree.SubElement(
            params, f"{_HP}stringParam", attrib={"name": name}
        )
        node.text = value

    _int_param("Prop", "0")
    _str_param("Command", command_value)
    _str_param("Path", url)
    _str_param("Category", category)
    _str_param("TargetType", "HWPHYPERLINK_TARGET_BOOKMARK")
    _str_param("DocOpenType", "HWPHYPERLINK_JUMP_CURRENTTAB")
    _str_param("ToolTip", tooltip)

    text_run = etree.Element(f"{_HP}run", attrib={"charPrIDRef": cp})
    t = etree.SubElement(text_run, f"{_HP}t")
    t.text = display

    end_run = etree.Element(f"{_HP}run", attrib={"charPrIDRef": cp})
    ctrl_end = etree.SubElement(end_run, f"{_HP}ctrl")
    etree.SubElement(
        ctrl_end,
        f"{_HP}fieldEnd",
        attrib={"beginIDRef": field_id, "fieldid": inst_id},
    )
    etree.SubElement(end_run, f"{_HP}t")
    return [begin_run, text_run, end_run]


def _make_run_with_equations(
    text: str,
    marks: list[dict[str, Any]],
    char_pr_id: str,
) -> etree._Element:
    """본문 ``hp:run`` 안에 평문과 수식 마커 텍스트를 번갈아 emit (Phase 9).

    각주와 달리 수식은 마커가 평문 텍스트이므로 ``hp:ctrl`` 없이 ``hp:t``
    만으로 처리된다. ``mapsi.math.converter.convert_equation`` 의 결과는
    이미 ``[hnc 수식]…[/hnc 수식]`` 마커로 감싸진 문자열이므로, 빌더는 그
    문자열을 그대로 ``hp:t`` 에 박기만 한다 (ADR 0002).

    Display equation 단락은 ``text=""`` 이고 ``marks=[{offset:0, ...}]`` 한
    개만 있는 형태로 들어온다 — 이 경우 빈 ``hp:t`` 1개 + 마커 ``hp:t``
    1개가 나온다. 한/글이 빈 ``hp:t`` 를 무난히 처리하므로 Inline 케이스의
    "빈 ``hp:t`` 회피" 와 동일한 정책 (offset 이 cursor 와 같으면 평문
    skip) 을 적용한다.

    Lazy import (``convert_equation``): 수식 없는 변환에서는 LLM SDK 를
    임포트하지 않도록 함수 안에서 import 한다.
    """
    from ..math.converter import convert_equation

    run = etree.Element(f"{_HP}run", attrib={"charPrIDRef": char_pr_id})
    sorted_marks = sorted(marks, key=lambda m: m.get("offset", 0))
    cursor = 0
    for mark in sorted_marks:
        offset = int(mark.get("offset", cursor))
        offset = max(cursor, min(offset, len(text)))
        if offset > cursor:
            t_before = etree.SubElement(run, f"{_HP}t")
            t_before.text = text[cursor:offset]
        marker_text = convert_equation(
            mark.get("latex", ""), bool(mark.get("display", False))
        )
        t_marker = etree.SubElement(run, f"{_HP}t")
        t_marker.text = marker_text
        cursor = offset
    if cursor < len(text):
        t_after = etree.SubElement(run, f"{_HP}t")
        t_after.text = text[cursor:]
    return run


def _make_run_with_footnotes(
    text: str,
    marks: list[dict[str, Any]],
    char_pr_id: str,
    style_map: dict[str, Any],
    style_table: dict[str, StyleEntry],
) -> etree._Element:
    """본문 ``hp:run`` 1 개에 평문 ``hp:t`` 와 각주 ``hp:ctrl`` 을 번갈아 emit.

    한/글 출력 패턴 (``samples/incremental/07_footnote/.../section0.xml``)::

        <hp:run charPrIDRef="...">
          <hp:t>마커 직전 텍스트</hp:t>
          <hp:ctrl>
            <hp:footNote .../>
          </hp:ctrl>
          <hp:t>마커 직후 텍스트</hp:t>
          ...
        </hp:run>

    마크는 ``offset`` 오름차순으로 정렬해 사용한다 (안전망; 파서/walker 가
    이미 정렬된 형태로 넘김). 인접 마크 사이에 평문이 비어 있어도 빈 문자
    ``hp:t`` 는 emit 하지 않는다 (한/글이 빈 ``hp:t`` 를 깔끔하게 다루지
    못함).
    """
    run = etree.Element(f"{_HP}run", attrib={"charPrIDRef": char_pr_id})
    sorted_marks = sorted(marks, key=lambda m: m.get("offset", 0))
    cursor = 0
    for mark in sorted_marks:
        offset = int(mark.get("offset", cursor))
        offset = max(cursor, min(offset, len(text)))
        if offset > cursor:
            t = etree.SubElement(run, f"{_HP}t")
            t.text = text[cursor:offset]
        ctrl = etree.SubElement(run, f"{_HP}ctrl")
        ctrl.append(_build_footnote(mark, style_map, style_table))
        cursor = offset
    if cursor < len(text):
        t = etree.SubElement(run, f"{_HP}t")
        t.text = text[cursor:]
    return run


def _build_footnote(
    mark: dict[str, Any],
    style_map: dict[str, Any],
    style_table: dict[str, StyleEntry],
) -> etree._Element:
    """``<hp:footNote>`` 노드 1 개를 만든다 (Phase 7).

    구조 (한/글 본가 출력과 동일)::

        <hp:footNote number="N" suffixChar="41" instId="...">
          <hp:subList ...>
            <hp:p styleIDRef="각주">
              <hp:run charPrIDRef="...">
                <hp:ctrl>
                  <hp:autoNum num="N" numType="FOOTNOTE">
                    <hp:autoNumFormat type="DIGIT" suffixChar=")"/>
                  </hp:autoNum>
                </hp:ctrl>
                <hp:t> 각주 본문</hp:t>
              </hp:run>
            </hp:p>
          </hp:subList>
        </hp:footNote>

    번호 ``N`` 은 ``mark["footnote_id"] + 1`` (0-base → 1-base). 한/글이
    문서 오픈 시 ``num`` 을 자동 재계산하나 명시적 값을 주는 것이 호환에
    안전하다. ``suffixChar="41"`` 은 ``)`` 의 ASCII (한/글 표준값).

    각주 본문 단락의 스타일은 ``style_map`` 의 ``footnote`` → ``"각주"``
    매핑을 따른다. 본문 텍스트 앞 공백 1개는 자동번호와 본문을 분리하는
    한/글 표기 관습.
    """
    fid = int(mark.get("footnote_id", 0))
    number = fid + 1
    body_text = mark.get("text") or ""

    name = style_name(style_map, "footnote", 0)
    if name not in style_table:
        raise KeyError(
            f"각주 스타일 이름 {name!r} 이 header.xml 에 정의돼 있지 않다"
        )
    entry = style_table[name]

    footnote = etree.Element(
        f"{_HP}footNote",
        attrib={
            "number": str(number),
            "suffixChar": "41",
            "instId": str(random.randint(1, 2**31 - 1)),
        },
    )
    sublist = etree.SubElement(
        footnote,
        f"{_HP}subList",
        attrib=_sublist_attrs(vert_align="TOP"),
    )
    p = etree.SubElement(
        sublist,
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
    run = etree.SubElement(
        p, f"{_HP}run", attrib={"charPrIDRef": entry.char_pr_id}
    )
    ctrl = etree.SubElement(run, f"{_HP}ctrl")
    auto_num = etree.SubElement(
        ctrl,
        f"{_HP}autoNum",
        attrib={"num": str(number), "numType": "FOOTNOTE"},
    )
    etree.SubElement(
        auto_num,
        f"{_HP}autoNumFormat",
        attrib={
            "type": "DIGIT",
            "userChar": "",
            "prefixChar": "",
            "suffixChar": ")",
            "supscript": "0",
        },
    )
    body_t = etree.SubElement(run, f"{_HP}t")
    body_t.text = " " + body_text
    return footnote


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


def build_figure_paragraph(
    block: Block,
    style_map: dict[str, Any],
    style_table: dict[str, StyleEntry],
    image_info: dict[str, Any] | None = None,
) -> etree._Element:
    """그림 ``hp:p`` (스타일 ``그림``) 를 생성한다.

    Parameters
    ----------
    block:
        ``role="figure"`` Block. ``meta["src"]`` 와 ``meta["caption"]`` 사용.
    style_map / style_table:
        :func:`build_paragraph` 와 동일.
    image_info:
        Phase 6b 모드 활성화 시 dict. None 이면 Phase 6a placeholder 모드
        (이미지 없는 단락; alt 텍스트만 보존). dict 키:
            - ``binary_item_id``: ``register_image`` 가 발급한 ID 문자열
            - ``width_hwpunit`` / ``height_hwpunit``: 환산된 그림 크기

    Returns
    -------
    lxml Element
        ``hp:p`` 노드. image_info 가 있으면 내부 ``hp:run`` 안에 ``hp:pic``
        (캡션 있으면 ``hp:caption`` 까지 포함) 이 들어가고 alt 텍스트는
        ``shapeComment`` 로 옮겨진다 (한/글 표준).
    """
    name = style_name(style_map, "figure", 0)
    if name not in style_table:
        raise KeyError(
            f"스타일 이름 {name!r} (role='figure') 이 header.xml 에 정의돼 있지 않다"
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
    if image_info is None:
        # Phase 6a placeholder: alt 텍스트만 보존
        p.append(_make_text_run(block.text, entry.char_pr_id))
        return p

    # Phase 6b: hp:pic 끼운 단락
    run = etree.SubElement(
        p, f"{_HP}run", attrib={"charPrIDRef": entry.char_pr_id}
    )
    pic = _build_pic(
        binary_item_id=str(image_info["binary_item_id"]),
        width_hwpunit=int(image_info["width_hwpunit"]),
        height_hwpunit=int(image_info["height_hwpunit"]),
        alt_text=block.text,
        caption=block.meta.get("caption"),
        caption_entry=(
            style_table[style_name(style_map, "figure_caption", 0)]
            if block.meta.get("caption")
            else None
        ),
    )
    run.append(pic)
    return p


def build_figure_caption_paragraph(
    text: str,
    style_map: dict[str, Any],
    style_table: dict[str, StyleEntry],
) -> etree._Element:
    """그림 캡션 ``hp:p`` (스타일 ``그림캡션``) 1 개를 생성한다 — Phase 6a.

    표 캡션과 동일하게 본문 앞에 ``hp:autoNum numType="PICTURE"`` 마커를
    삽입해 한/글이 "그림 N" 번호를 자동 부여하도록 한다. ``num`` 속성은
    한/글이 문서 오픈 시 재계산하므로 우리는 ``"1"`` 로 고정.

    Phase 6b 에서 캡션이 ``hp:pic`` 내부의 ``hp:caption`` 으로 이동하면
    이 함수는 폐기될 예정이다 (표와 동일한 캡션 모델로 통합).
    """
    name = style_name(style_map, "figure_caption", 0)
    if name not in style_table:
        raise KeyError(
            f"스타일 이름 {name!r} (role='figure_caption') 이 header.xml 에 정의돼 있지 않다"
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
    run = etree.SubElement(p, f"{_HP}run", attrib={"charPrIDRef": entry.char_pr_id})
    prefix_t = etree.SubElement(run, f"{_HP}t")
    prefix_t.text = "그림 "
    ctrl = etree.SubElement(run, f"{_HP}ctrl")
    auto_num = etree.SubElement(
        ctrl,
        f"{_HP}autoNum",
        attrib={"num": "1", "numType": "PICTURE"},
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
    return p


# ---------------------------------------------------------------------------
# hp:pic (그림 노드) 빌더 — Phase 6b
# ---------------------------------------------------------------------------

# 한/글 외부 좌표계와의 정합을 위한 상수.
HC_NS = "http://www.hancom.co.kr/hwpml/2011/core"
_HC = f"{{{HC_NS}}}"

_FIGURE_OUT_MARGIN = (0, 283, 283, 283)  # (left, right, top, bottom) HWPUNIT
_FIGURE_IN_MARGIN = (0, 0, 0, 0)
_FIGURE_CAPTION_WIDTH = 8504
_FIGURE_CAPTION_GAP = 850


def _build_pic(
    binary_item_id: str,
    width_hwpunit: int,
    height_hwpunit: int,
    alt_text: str,
    caption: str | None,
    caption_entry: StyleEntry | None,
) -> etree._Element:
    """``<hp:pic>`` 노드 1 개를 생성한다.

    Parameters
    ----------
    binary_item_id:
        ``content.hpf`` 의 ``opf:item`` id (= ``register_image`` 발급).
        ``hc:img binaryItemIDRef`` 가 이 값을 참조한다.
    width_hwpunit / height_hwpunit:
        그림의 표시 크기 (HWPUNIT). 원본 크기와 표시 크기를 동일하게
        설정해 한/글에서 변형 없이 보이도록 한다.
    alt_text:
        대체 텍스트. ``hp:shapeComment`` 로 옮겨 한/글 접근성 검사기가
        읽도록 한다. 빈 문자열이면 shapeComment 자체를 생성하지 않는다.
    caption:
        캡션 본문 (정제 후, 접두사 제거). None 이면 ``hp:caption`` 노드를
        만들지 않는다.
    caption_entry:
        ``style_table["그림캡션"]``. caption 이 있으면 필수.

    Returns
    -------
    lxml Element
        ``<hp:pic>`` 요소. 한/글이 인식하는 모든 필수 속성/자식을 포함.

    Notes
    -----
    한/글이 ``hp:pic`` 을 그릴 때 요구하는 필수 자식 노드 순서는 샘플
    HWPX (``samples/incremental/06_figure``) 의 출력값을 그대로 따른다.
    렌더링 매트릭스 (``hc:scaMatrix`` 등) 는 한/글이 문서 오픈 시
    재계산하므로 항등 행렬로 둔다.
    """
    pic = etree.Element(
        f"{_HP}pic",
        attrib={
            "id": str(random.randint(1, 2**31 - 1)),
            "zOrder": "0",
            "numberingType": "PICTURE",
            "textWrap": "TOP_AND_BOTTOM",
            "textFlow": "BOTH_SIDES",
            "lock": "0",
            "dropcapstyle": "None",
            "href": "",
            "groupLevel": "0",
            "instid": str(random.randint(1, 2**31 - 1)),
            "reverse": "0",
        },
    )
    etree.SubElement(pic, f"{_HP}offset", attrib={"x": "0", "y": "0"})
    etree.SubElement(
        pic,
        f"{_HP}orgSz",
        attrib={"width": str(width_hwpunit), "height": str(height_hwpunit)},
    )
    etree.SubElement(
        pic,
        f"{_HP}curSz",
        attrib={"width": str(width_hwpunit), "height": str(height_hwpunit)},
    )
    etree.SubElement(
        pic, f"{_HP}flip", attrib={"horizontal": "0", "vertical": "0"}
    )
    etree.SubElement(
        pic,
        f"{_HP}rotationInfo",
        attrib={
            "angle": "0",
            "centerX": str(width_hwpunit // 2),
            "centerY": str(height_hwpunit // 2),
            "rotateimage": "1",
        },
    )
    rendering = etree.SubElement(pic, f"{_HP}renderingInfo")
    for tag in ("transMatrix", "scaMatrix", "rotMatrix"):
        etree.SubElement(
            rendering,
            f"{_HC}{tag}",
            attrib={
                "e1": "1",
                "e2": "0",
                "e3": "0",
                "e4": "0",
                "e5": "1",
                "e6": "0",
            },
        )
    etree.SubElement(
        pic,
        f"{_HC}img",
        attrib={
            "binaryItemIDRef": binary_item_id,
            "bright": "0",
            "contrast": "0",
            "effect": "REAL_PIC",
            "alpha": "0",
        },
    )
    img_rect = etree.SubElement(pic, f"{_HP}imgRect")
    for i, (x, y) in enumerate(
        [
            (0, 0),
            (width_hwpunit, 0),
            (width_hwpunit, height_hwpunit),
            (0, height_hwpunit),
        ]
    ):
        etree.SubElement(
            img_rect, f"{_HC}pt{i}", attrib={"x": str(x), "y": str(y)}
        )
    etree.SubElement(
        pic,
        f"{_HP}imgClip",
        attrib={
            "left": "0",
            "right": str(width_hwpunit),
            "top": "0",
            "bottom": str(height_hwpunit),
        },
    )
    etree.SubElement(
        pic, f"{_HP}inMargin", attrib=_margin_attrs(_FIGURE_IN_MARGIN)
    )
    etree.SubElement(
        pic,
        f"{_HP}imgDim",
        attrib={
            "dimwidth": str(width_hwpunit),
            "dimheight": str(height_hwpunit),
        },
    )
    etree.SubElement(pic, f"{_HP}effects")
    etree.SubElement(
        pic,
        f"{_HP}sz",
        attrib={
            "width": str(width_hwpunit),
            "widthRelTo": "ABSOLUTE",
            "height": str(height_hwpunit),
            "heightRelTo": "ABSOLUTE",
            "protect": "0",
        },
    )
    etree.SubElement(
        pic,
        f"{_HP}pos",
        attrib={
            "treatAsChar": "1",
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
        pic, f"{_HP}outMargin", attrib=_margin_attrs(_FIGURE_OUT_MARGIN)
    )
    if alt_text:
        comment = etree.SubElement(pic, f"{_HP}shapeComment")
        comment.text = alt_text
    if caption is not None:
        if caption_entry is None:
            raise ValueError("caption 이 있으면 caption_entry 가 필수")
        pic.append(_build_pic_caption(caption, caption_entry, width_hwpunit))
    return pic


def _build_pic_caption(
    text: str, caption_entry: StyleEntry, ref_width_hwpunit: int
) -> etree._Element:
    """``hp:pic`` 내부 ``<hp:caption>`` 노드를 만든다.

    표 캡션 (:func:`_build_caption`) 과 거의 동일하지만:
        - ``side="BOTTOM"`` (그림 캡션은 그림 아래)
        - ``lastWidth`` 는 그림 폭 기반 (표는 표 폭 기반)
        - autoNum 의 ``numType="PICTURE"``
    """
    caption = etree.Element(
        f"{_HP}caption",
        attrib={
            "side": "BOTTOM",
            "fullSz": "0",
            "width": str(_FIGURE_CAPTION_WIDTH),
            "gap": str(_FIGURE_CAPTION_GAP),
            "lastWidth": str(ref_width_hwpunit),
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
    prefix_t.text = "그림 "
    ctrl = etree.SubElement(run, f"{_HP}ctrl")
    auto_num = etree.SubElement(
        ctrl,
        f"{_HP}autoNum",
        attrib={"num": "1", "numType": "PICTURE"},
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


def build_picture(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """그림(hp:pic) 노드를 생성한다 — 외부 호출용 래퍼.

    Phase 6b 의 본체는 :func:`_build_pic` (private). 본 함수는 호환을 위해
    스텁으로 남겨두었으며 직접 호출을 권장하지 않는다.
    """
    raise NotImplementedError(
        "build_picture 는 외부에서 직접 호출하지 않는다. "
        "build_figure_paragraph(..., image_info=...) 를 사용할 것."
    )


def build_footnote_ref(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """레거시 자리표시. Phase 7 부터는 ``build_paragraph`` 가 직접 처리한다.

    실제 hp:footNote XML 은 :func:`_build_footnote` 가 ``build_paragraph``
    내부에서 호출되어 본문 ``hp:run`` 안에 끼워 emit 한다 (한/글 본가
    출력과 동일 구조). 본 함수는 시그니처 호환을 위해 남겨 두며 호출 시
    명시적으로 차단한다.
    """
    raise NotImplementedError(
        "build_footnote_ref 는 외부에서 직접 호출하지 않는다. "
        "build_paragraph 가 block.meta['footnote_marks'] 를 보고 "
        "hp:footNote 를 직접 emit 한다."
    )
