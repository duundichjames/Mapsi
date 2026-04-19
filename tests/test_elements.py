"""``mapsi.builder.elements.build_paragraph`` 의 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.builder.elements import build_paragraph
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
