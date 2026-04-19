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
