"""``mapsi.builder.elements.build_paragraph`` 의 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.builder.elements import (
    build_figure_caption_paragraph,
    build_figure_paragraph,
    build_paragraph,
    build_table_wrapper,
)
from mapsi.builder.header import load_header, parse_style_table
from mapsi.config import load_style_map
from mapsi.parser import Block


HP_NS = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


@pytest.fixture(scope="module")
def style_table(templates_dir: Path):
    return parse_style_table(load_header(templates_dir / "Contents" / "header.xml"))


@pytest.fixture(scope="module")
def style_map(spec_dir: Path):
    return load_style_map(spec_dir / "styles.yaml")


def test_paragraph_block_produces_본문_styled_p(style_map, style_table) -> None:
    block = Block(role="paragraph", text="안녕")
    p = build_paragraph(block, style_map, style_table)
    assert p.tag == f"{HP_NS}p"
    assert p.get("styleIDRef") == "3"  # spec/styles.yaml: paragraph -> id 3 (본문)
    assert p.get("paraPrIDRef") == "18"  # 본문 의 paraPrIDRef
    run = p.find(f"{HP_NS}run")
    assert run is not None
    assert run.get("charPrIDRef") == "7"
    t = run.find(f"{HP_NS}t")
    assert t is not None
    assert t.text == "안녕"


@pytest.mark.parametrize(
    "depth,sid,ppid,cpid",
    [
        (1, "4", "20", "12"),   # 개요 1
        (2, "5", "22", "13"),   # 개요 2
        (3, "6", "23", "13"),   # 개요 3
        (4, "7", "24", "14"),   # 개요 4
        (5, "17", "25", "15"),  # 개요 5
    ],
)
def test_heading_blocks_use_correct_outline_styles(
    style_map, style_table, depth, sid, ppid, cpid
) -> None:
    block = Block(role="heading", depth=depth, text=f"제목 {depth}")
    p = build_paragraph(block, style_map, style_table)
    assert p.get("styleIDRef") == sid
    assert p.get("paraPrIDRef") == ppid
    run = p.find(f"{HP_NS}run")
    assert run is not None
    assert run.get("charPrIDRef") == cpid


def test_empty_text_produces_run_without_t(style_map, style_table) -> None:
    block = Block(role="paragraph", text="")
    p = build_paragraph(block, style_map, style_table)
    run = p.find(f"{HP_NS}run")
    assert run is not None
    assert run.find(f"{HP_NS}t") is None


def test_required_attrs_are_present(style_map, style_table) -> None:
    block = Block(role="paragraph", text="x")
    p = build_paragraph(block, style_map, style_table)
    for attr in ("id", "paraPrIDRef", "styleIDRef", "pageBreak", "columnBreak", "merged"):
        assert p.get(attr) is not None, f"hp:p 의 {attr!r} 속성 누락"


# ---------------------------------------------------------------------------
# build_table_wrapper
# ---------------------------------------------------------------------------


def _make_table_block(
    rows: list[list[str]], caption: str | None = None
) -> Block:
    return Block(role="table", meta={"rows": rows, "caption": caption})


class TestBuildTableWrapper:
    def test_returns_wrapper_paragraph_with_tbl_inside(
        self, style_map, style_table
    ) -> None:
        wrapper = build_table_wrapper(
            _make_table_block([["a", "b"], ["1", "2"]]), style_map, style_table
        )
        assert wrapper.tag == f"{HP_NS}p"
        run = wrapper.find(f"{HP_NS}run")
        assert run is not None
        tbl = run.find(f"{HP_NS}tbl")
        assert tbl is not None
        assert tbl.get("rowCnt") == "2"
        assert tbl.get("colCnt") == "2"

    def test_wrapper_uses_본문_style(self, style_map, style_table) -> None:
        wrapper = build_table_wrapper(
            _make_table_block([["x"]]), style_map, style_table
        )
        # 본문 = id 3
        assert wrapper.get("styleIDRef") == "3"

    def test_cells_use_표내용_style(self, style_map, style_table) -> None:
        wrapper = build_table_wrapper(
            _make_table_block([["a", "b"]]), style_map, style_table
        )
        cells = wrapper.findall(
            f"{HP_NS}run/{HP_NS}tbl/{HP_NS}tr/{HP_NS}tc"
        )
        assert len(cells) == 2
        for tc in cells:
            p = tc.find(f"{HP_NS}subList/{HP_NS}p")
            assert p is not None
            # 표내용 = id 33
            assert p.get("styleIDRef") == "33"

    def test_cell_text_is_emitted(self, style_map, style_table) -> None:
        wrapper = build_table_wrapper(
            _make_table_block([["가", "나"], ["다", "라"]]),
            style_map,
            style_table,
        )
        ts = wrapper.findall(
            f"{HP_NS}run/{HP_NS}tbl/{HP_NS}tr/{HP_NS}tc/"
            f"{HP_NS}subList/{HP_NS}p/{HP_NS}run/{HP_NS}t"
        )
        assert [t.text for t in ts] == ["가", "나", "다", "라"]

    def test_cell_addresses_are_set(self, style_map, style_table) -> None:
        wrapper = build_table_wrapper(
            _make_table_block([["a", "b"], ["c", "d"]]), style_map, style_table
        )
        addrs = [
            (a.get("colAddr"), a.get("rowAddr"))
            for a in wrapper.iter(f"{HP_NS}cellAddr")
        ]
        assert addrs == [("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")]

    def test_caption_is_omitted_when_none(self, style_map, style_table) -> None:
        wrapper = build_table_wrapper(
            _make_table_block([["x"]]), style_map, style_table
        )
        assert wrapper.find(f"{HP_NS}run/{HP_NS}tbl/{HP_NS}caption") is None

    def test_caption_is_emitted_when_present(self, style_map, style_table) -> None:
        wrapper = build_table_wrapper(
            _make_table_block([["x"]], caption="분기별 매출"),
            style_map,
            style_table,
        )
        caption = wrapper.find(f"{HP_NS}run/{HP_NS}tbl/{HP_NS}caption")
        assert caption is not None
        # 표캡션 = id 11
        cap_p = caption.find(f"{HP_NS}subList/{HP_NS}p")
        assert cap_p is not None
        assert cap_p.get("styleIDRef") == "11"

    def test_caption_uses_autonum_pattern(self, style_map, style_table) -> None:
        """캡션은 ``<hp:t>표 </hp:t><autoNum/><hp:t> 본문</hp:t>`` 패턴."""
        wrapper = build_table_wrapper(
            _make_table_block([["x"]], caption="분기별 매출"),
            style_map,
            style_table,
        )
        run = wrapper.find(
            f"{HP_NS}run/{HP_NS}tbl/{HP_NS}caption/{HP_NS}subList/"
            f"{HP_NS}p/{HP_NS}run"
        )
        assert run is not None
        ts = run.findall(f"{HP_NS}t")
        assert [t.text for t in ts] == ["표 ", " 분기별 매출"]
        auto_num = run.find(f"{HP_NS}ctrl/{HP_NS}autoNum")
        assert auto_num is not None
        assert auto_num.get("numType") == "TABLE"

    def test_jagged_rows_are_padded(self, style_map, style_table) -> None:
        """행마다 셀 개수가 다르면 colCnt 만큼 빈 셀로 패딩."""
        wrapper = build_table_wrapper(
            _make_table_block([["a", "b", "c"], ["x"]]), style_map, style_table
        )
        tbl = wrapper.find(f"{HP_NS}run/{HP_NS}tbl")
        assert tbl is not None
        assert tbl.get("colCnt") == "3"
        rows = tbl.findall(f"{HP_NS}tr")
        assert len(rows[1].findall(f"{HP_NS}tc")) == 3

    def test_empty_rows_raises(self, style_map, style_table) -> None:
        with pytest.raises(ValueError, match="rows"):
            build_table_wrapper(
                _make_table_block([]), style_map, style_table
            )


# ---------------------------------------------------------------------------
# build_figure_paragraph / build_figure_caption_paragraph (Phase 6a)
# ---------------------------------------------------------------------------


def _make_figure_block(
    src: str, alt: str = "", caption: str | None = None
) -> Block:
    return Block(role="figure", text=alt, meta={"src": src, "caption": caption})


class TestBuildFigureParagraph:
    def test_returns_그림_styled_paragraph(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="alt"), style_map, style_table
        )
        assert p.tag == f"{HP_NS}p"
        # 그림 = id 2 in templates/Contents/header.xml
        assert p.get("styleIDRef") == "2"
        assert p.get("paraPrIDRef") == "28"

    def test_alt_text_is_emitted_as_placeholder(
        self, style_map, style_table
    ) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="개요도"), style_map, style_table
        )
        t = p.find(f"{HP_NS}run/{HP_NS}t")
        assert t is not None
        assert t.text == "개요도"

    def test_empty_alt_omits_t_node(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt=""), style_map, style_table
        )
        run = p.find(f"{HP_NS}run")
        assert run is not None
        assert run.find(f"{HP_NS}t") is None

    def test_required_attrs_present(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png"), style_map, style_table
        )
        for attr in (
            "id",
            "paraPrIDRef",
            "styleIDRef",
            "pageBreak",
            "columnBreak",
            "merged",
        ):
            assert p.get(attr) is not None, f"hp:p 의 {attr!r} 속성 누락"


class TestBuildFigureParagraphWithPic:
    """``image_info`` 가 주어진 Phase 6b 모드 — 실 hp:pic 발급."""

    image_info = {
        "binary_item_id": "image1",
        "width_hwpunit": 15000,
        "height_hwpunit": 9000,
    }

    def test_run_contains_pic_node(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="diagram"),
            style_map,
            style_table,
            image_info=self.image_info,
        )
        run = p.find(f"{HP_NS}run")
        assert run is not None
        pic = run.find(f"{HP_NS}pic")
        assert pic is not None

    def test_pic_has_required_children_in_order(
        self, style_map, style_table
    ) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="x"),
            style_map,
            style_table,
            image_info=self.image_info,
        )
        pic = p.find(f"{HP_NS}run/{HP_NS}pic")
        children = [etree_qname_local(c.tag) for c in pic]
        # 핵심 자식 노드들 (한/글이 거부하지 않는 최소 집합) 이 모두 존재.
        for required in (
            "offset",
            "orgSz",
            "curSz",
            "renderingInfo",
            "img",
            "imgRect",
            "imgClip",
            "sz",
            "pos",
        ):
            assert required in children, f"hp:pic 의 {required!r} 누락"

    def test_img_references_binary_item_id(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="x"),
            style_map,
            style_table,
            image_info={"binary_item_id": "image42", "width_hwpunit": 100, "height_hwpunit": 100},
        )
        img = p.find(f".//{{{HC_NS}}}img")
        assert img is not None
        assert img.get("binaryItemIDRef") == "image42"

    def test_orgSz_curSz_use_hwpunit_values(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="x"),
            style_map,
            style_table,
            image_info=self.image_info,
        )
        org = p.find(f".//{HP_NS}orgSz")
        cur = p.find(f".//{HP_NS}curSz")
        assert (org.get("width"), org.get("height")) == ("15000", "9000")
        assert (cur.get("width"), cur.get("height")) == ("15000", "9000")

    def test_alt_text_goes_into_shape_comment(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="대체 텍스트"),
            style_map,
            style_table,
            image_info=self.image_info,
        )
        comment = p.find(f".//{HP_NS}shapeComment")
        assert comment is not None
        assert comment.text == "대체 텍스트"
        # placeholder 모드와 달리 hp:t 는 없어야 함 (이중 노출 방지).
        # hp:caption 안의 hp:t 는 caption 없는 케이스이므로 없음.
        ts_outside_pic = [
            t for t in p.iter(f"{HP_NS}t")
            if t.getparent() is None or t.getparent().getparent() is not None
        ]
        # caption 없으므로 hp:pic 안에도 hp:t 없음 → 전체 hp:t 0
        assert p.find(f"{HP_NS}run/{HP_NS}t") is None

    def test_no_alt_omits_shape_comment(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt=""),
            style_map,
            style_table,
            image_info=self.image_info,
        )
        assert p.find(f".//{HP_NS}shapeComment") is None

    def test_caption_absorbed_into_pic(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="x", caption="흐름도"),
            style_map,
            style_table,
            image_info=self.image_info,
        )
        caption = p.find(f".//{HP_NS}caption")
        assert caption is not None
        assert caption.get("side") == "BOTTOM"
        # autoNum numType=PICTURE
        auto_num = caption.find(f".//{HP_NS}autoNum")
        assert auto_num is not None
        assert auto_num.get("numType") == "PICTURE"
        # 캡션 본문 텍스트 (접미부) 가 hp:t 로 들어감
        ts = [t.text for t in caption.iter(f"{HP_NS}t") if t.text]
        assert any("흐름도" in t for t in ts)

    def test_no_caption_omits_caption_node(self, style_map, style_table) -> None:
        p = build_figure_paragraph(
            _make_figure_block("a.png", alt="x"),
            style_map,
            style_table,
            image_info=self.image_info,
        )
        assert p.find(f".//{HP_NS}caption") is None


def etree_qname_local(tag: str) -> str:
    """``{ns}local`` 형태에서 ``local`` 만 추출."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


HC_NS = "http://www.hancom.co.kr/hwpml/2011/core"


class TestBuildFigureCaptionParagraph:
    def test_returns_그림캡션_styled_paragraph(
        self, style_map, style_table
    ) -> None:
        p = build_figure_caption_paragraph("개요", style_map, style_table)
        assert p.tag == f"{HP_NS}p"
        # 그림캡션 = id 1
        assert p.get("styleIDRef") == "1"
        assert p.get("paraPrIDRef") == "30"

    def test_emits_autonum_with_picture_type(
        self, style_map, style_table
    ) -> None:
        p = build_figure_caption_paragraph("본문", style_map, style_table)
        auto_num = p.find(f"{HP_NS}run/{HP_NS}ctrl/{HP_NS}autoNum")
        assert auto_num is not None
        assert auto_num.get("numType") == "PICTURE"
        assert auto_num.get("num") == "1"

    def test_caption_text_uses_prefix_and_body_pattern(
        self, style_map, style_table
    ) -> None:
        """``<hp:t>그림 </hp:t><autoNum/><hp:t> 본문</hp:t>`` 패턴."""
        p = build_figure_caption_paragraph("개요도", style_map, style_table)
        ts = p.findall(f"{HP_NS}run/{HP_NS}t")
        assert [t.text for t in ts] == ["그림 ", " 개요도"]

    def test_autonum_format_attrs(self, style_map, style_table) -> None:
        p = build_figure_caption_paragraph("x", style_map, style_table)
        fmt = p.find(
            f"{HP_NS}run/{HP_NS}ctrl/{HP_NS}autoNum/{HP_NS}autoNumFormat"
        )
        assert fmt is not None
        assert fmt.get("type") == "DIGIT"


# ===========================================================================
# Phase 7 — 각주 (footnote) 임베드
# ===========================================================================


class TestBuildParagraphWithFootnotes:
    """``build_paragraph`` 가 ``meta["footnote_marks"]`` 를 보고 hp:footNote 를
    인라인으로 끼워 emit 하는지 검증.

    참고 구조 (한/글 본가 출력)::

        <hp:p ...>
          <hp:run charPrIDRef="...">
            <hp:t>마커 직전</hp:t>
            <hp:ctrl>
              <hp:footNote number="N" ...>
                <hp:subList ...>
                  <hp:p styleIDRef="각주">
                    <hp:run>
                      <hp:ctrl><hp:autoNum num="N" numType="FOOTNOTE"/></hp:ctrl>
                      <hp:t> 본문</hp:t>
                    </hp:run>
                  </hp:p>
                </hp:subList>
              </hp:footNote>
            </hp:ctrl>
            <hp:t>마커 직후</hp:t>
          </hp:run>
        </hp:p>
    """

    def _make_block(
        self, text: str, marks: list[dict]
    ) -> Block:
        return Block(role="paragraph", text=text, meta={"footnote_marks": marks})

    def test_no_footnote_marks_falls_back_to_plain_run(
        self, style_map, style_table
    ) -> None:
        """마크가 없으면 기존 단일 hp:t 경로와 동일하게 동작."""
        block = Block(role="paragraph", text="평범", meta={})
        p = build_paragraph(block, style_map, style_table)
        run = p.find(f"{HP_NS}run")
        assert run is not None
        ts = run.findall(f"{HP_NS}t")
        ctrls = run.findall(f"{HP_NS}ctrl")
        assert len(ts) == 1 and ts[0].text == "평범"
        assert ctrls == []

    def test_single_footnote_splits_text_into_two_t_around_ctrl(
        self, style_map, style_table
    ) -> None:
        """마커 1 개면 hp:t / hp:ctrl(footNote) / hp:t 의 3 자식 시퀀스."""
        block = self._make_block(
            "고향은 산골.",
            [{"kind": "footnote_ref", "offset": 2, "footnote_id": 0,
              "text": "각주 본문."}],
        )
        p = build_paragraph(block, style_map, style_table)
        run = p.find(f"{HP_NS}run")
        # children 순서 보존 확인
        kids = list(run)
        kid_tags = [k.tag for k in kids]
        assert kid_tags == [f"{HP_NS}t", f"{HP_NS}ctrl", f"{HP_NS}t"]
        assert kids[0].text == "고향"
        assert kids[2].text == "은 산골."

    def test_footnote_at_end_omits_trailing_t(
        self, style_map, style_table
    ) -> None:
        """마커가 끝에 있으면 뒤쪽 빈 hp:t 는 emit 안 함."""
        block = self._make_block(
            "끝!",
            [{"kind": "footnote_ref", "offset": 3, "footnote_id": 0,
              "text": "주."}],
        )
        p = build_paragraph(block, style_map, style_table)
        run = p.find(f"{HP_NS}run")
        kid_tags = [k.tag for k in run]
        assert kid_tags == [f"{HP_NS}t", f"{HP_NS}ctrl"]

    def test_footnote_at_start_omits_leading_t(
        self, style_map, style_table
    ) -> None:
        """마커가 0 위치에 있으면 앞쪽 빈 hp:t 는 emit 안 함."""
        block = self._make_block(
            "본문.",
            [{"kind": "footnote_ref", "offset": 0, "footnote_id": 0,
              "text": "주."}],
        )
        p = build_paragraph(block, style_map, style_table)
        run = p.find(f"{HP_NS}run")
        kid_tags = [k.tag for k in run]
        assert kid_tags == [f"{HP_NS}ctrl", f"{HP_NS}t"]

    def test_multiple_footnotes_alternate_in_order(
        self, style_map, style_table
    ) -> None:
        """마커 N 개면 (N+1) 개 미만의 hp:t 와 N 개의 hp:ctrl 이 교차."""
        block = self._make_block(
            "AA BB CC.",
            [
                {"kind": "footnote_ref", "offset": 2, "footnote_id": 0,
                 "text": "일."},
                {"kind": "footnote_ref", "offset": 5, "footnote_id": 1,
                 "text": "이."},
            ],
        )
        p = build_paragraph(block, style_map, style_table)
        run = p.find(f"{HP_NS}run")
        ctrls = run.findall(f"{HP_NS}ctrl")
        ts = run.findall(f"{HP_NS}t")
        assert len(ctrls) == 2
        assert [t.text for t in ts] == ["AA", " BB", " CC."]

    def test_marks_are_sorted_by_offset_defensively(
        self, style_map, style_table
    ) -> None:
        """offset 이 역순으로 들어와도 정렬 후 emit (안전망)."""
        block = self._make_block(
            "AA BB.",
            [
                {"kind": "footnote_ref", "offset": 5, "footnote_id": 1,
                 "text": "이."},
                {"kind": "footnote_ref", "offset": 2, "footnote_id": 0,
                 "text": "일."},
            ],
        )
        p = build_paragraph(block, style_map, style_table)
        run = p.find(f"{HP_NS}run")
        ts = run.findall(f"{HP_NS}t")
        assert [t.text for t in ts] == ["AA", " BB", "."]

    def test_footnote_node_uses_footnote_style(
        self, style_map, style_table
    ) -> None:
        """각주 본문 단락은 styles.yaml 의 'footnote' → '각주' 스타일을 쓴다.

        header.xml 에서 '각주' 는 styleIDRef=25, paraPrIDRef=7, charPrIDRef=10.
        """
        block = self._make_block(
            "본문.",
            [{"kind": "footnote_ref", "offset": 2, "footnote_id": 0,
              "text": "주."}],
        )
        p = build_paragraph(block, style_map, style_table)
        footnote = p.find(f".//{HP_NS}footNote")
        assert footnote is not None
        inner_p = footnote.find(f"{HP_NS}subList/{HP_NS}p")
        assert inner_p is not None
        assert inner_p.get("styleIDRef") == "25"
        assert inner_p.get("paraPrIDRef") == "7"
        inner_run = inner_p.find(f"{HP_NS}run")
        assert inner_run.get("charPrIDRef") == "10"

    def test_footnote_number_is_footnote_id_plus_one(
        self, style_map, style_table
    ) -> None:
        """hp:footNote@number 와 hp:autoNum@num 은 (id + 1) 의 1-base 값."""
        block = self._make_block(
            "AA BB.",
            [
                {"kind": "footnote_ref", "offset": 2, "footnote_id": 0,
                 "text": "일."},
                {"kind": "footnote_ref", "offset": 5, "footnote_id": 1,
                 "text": "이."},
            ],
        )
        p = build_paragraph(block, style_map, style_table)
        notes = p.findall(f".//{HP_NS}footNote")
        assert [n.get("number") for n in notes] == ["1", "2"]
        autos = p.findall(f".//{HP_NS}autoNum")
        assert [a.get("num") for a in autos] == ["1", "2"]
        assert all(a.get("numType") == "FOOTNOTE" for a in autos)

    def test_footnote_body_text_is_prefixed_with_one_space(
        self, style_map, style_table
    ) -> None:
        """본문 hp:t 앞에 공백 1개 (한/글 표기 관습)."""
        block = self._make_block(
            "본문.",
            [{"kind": "footnote_ref", "offset": 2, "footnote_id": 0,
              "text": "각주."}],
        )
        p = build_paragraph(block, style_map, style_table)
        body_t = p.find(
            f".//{HP_NS}footNote//{HP_NS}p//{HP_NS}run/{HP_NS}t"
        )
        assert body_t is not None
        assert body_t.text == " 각주."

    def test_footnote_with_empty_body_still_emits_node(
        self, style_map, style_table
    ) -> None:
        """정의가 없는 마크 (text='') 도 hp:footNote 노드는 emit, 본문은 빈 공백."""
        block = self._make_block(
            "고아.",
            [{"kind": "footnote_ref", "offset": 2, "footnote_id": 0,
              "text": ""}],
        )
        p = build_paragraph(block, style_map, style_table)
        body_t = p.find(
            f".//{HP_NS}footNote//{HP_NS}p//{HP_NS}run/{HP_NS}t"
        )
        # 정의가 없어도 " " (공백 1개) 는 보존 (한/글 패턴 일관성)
        assert body_t is not None
        assert body_t.text == " "


# ---------------------------------------------------------------------------
# Phase 9: 수식 마커 빌더 (`equation_marks`)
# ---------------------------------------------------------------------------


class TestEquationParagraph:
    """``meta["equation_marks"]`` 가 있는 paragraph 의 빌드 결과 검증.

    세션 conftest 가 ``MAPSI_NO_LLM=1`` 을 강제하므로 모든 마커 본문은
    LaTeX 원문 그대로 ``[hnc 수식]…[/hnc 수식]`` 으로 박힌다.
    """

    @staticmethod
    def _make_block(text: str, marks: list[dict]) -> Block:
        return Block(
            role="paragraph",
            text=text,
            meta={"equation_marks": marks},
        )

    def test_inline_equation_emits_marker_text_in_run(
        self, style_map, style_table
    ) -> None:
        block = self._make_block(
            "본문  입니다.",
            [{"offset": 3, "latex": "a^2+b^2", "display": False}],
        )
        p = build_paragraph(block, style_map, style_table)
        assert p.get("styleIDRef") == "3"  # 본문
        run = p.find(f"{HP_NS}run")
        ts = run.findall(f"{HP_NS}t")
        # 평문 앞 / 마커 / 평문 뒤 = 3 개의 hp:t
        assert [t.text for t in ts] == [
            "본문 ",
            "[hnc 수식]a^2+b^2[/hnc 수식]",
            " 입니다.",
        ]

    def test_inline_equation_at_start_skips_leading_empty_t(
        self, style_map, style_table
    ) -> None:
        block = self._make_block(
            " 는 변수.",
            [{"offset": 0, "latex": "x", "display": False}],
        )
        p = build_paragraph(block, style_map, style_table)
        ts = p.find(f"{HP_NS}run").findall(f"{HP_NS}t")
        assert [t.text for t in ts] == [
            "[hnc 수식]x[/hnc 수식]",
            " 는 변수.",
        ]

    def test_inline_equation_at_end_skips_trailing_empty_t(
        self, style_map, style_table
    ) -> None:
        block = self._make_block(
            "수식 ",
            [{"offset": 3, "latex": "y", "display": False}],
        )
        p = build_paragraph(block, style_map, style_table)
        ts = p.find(f"{HP_NS}run").findall(f"{HP_NS}t")
        assert [t.text for t in ts] == [
            "수식 ",
            "[hnc 수식]y[/hnc 수식]",
        ]

    def test_multiple_inline_equations_in_order(
        self, style_map, style_table
    ) -> None:
        block = self._make_block(
            "값  와  의 합  입니다.",
            [
                {"offset": 2, "latex": "a", "display": False},
                {"offset": 5, "latex": "b", "display": False},
                {"offset": 10, "latex": "c", "display": False},
            ],
        )
        p = build_paragraph(block, style_map, style_table)
        ts = [t.text for t in p.find(f"{HP_NS}run").findall(f"{HP_NS}t")]
        assert ts == [
            "값 ",
            "[hnc 수식]a[/hnc 수식]",
            " 와 ",
            "[hnc 수식]b[/hnc 수식]",
            " 의 합 ",
            "[hnc 수식]c[/hnc 수식]",
            " 입니다.",
        ]

    def test_display_equation_paragraph_uses_본문_style(
        self, style_map, style_table
    ) -> None:
        """디스플레이 수식 단락도 본문 스타일을 그대로 사용 (ADR 0002)."""
        block = self._make_block(
            "",
            [{"offset": 0, "latex": "\\frac{a}{b}", "display": True}],
        )
        p = build_paragraph(block, style_map, style_table)
        assert p.get("styleIDRef") == "3"  # 본문 (수식 전용 스타일 없음)
        ts = [t.text for t in p.find(f"{HP_NS}run").findall(f"{HP_NS}t")]
        assert ts == ["[hnc 수식]\\frac{a}{b}[/hnc 수식]"]

    def test_footnote_and_equation_both_present_raises(
        self, style_map, style_table
    ) -> None:
        block = Block(
            role="paragraph",
            text="x",
            meta={
                "footnote_marks": [
                    {"kind": "footnote_ref", "offset": 0,
                     "footnote_id": 0, "text": "주."}
                ],
                "equation_marks": [
                    {"offset": 1, "latex": "y", "display": False}
                ],
            },
        )
        with pytest.raises(NotImplementedError, match="동시에"):
            build_paragraph(block, style_map, style_table)
