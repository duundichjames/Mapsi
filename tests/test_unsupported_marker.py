"""미처리 표식 폴백 검증.

의도된 미지원(UnsupportedFeature) 은 변환을 중단하지 않고 해당 블록을
〔MAPSI 미처리: 원문〕 표식 단락으로 대체한다. 진짜 오류(다른 예외 타입) 는
그대로 전파되어 표식이 버그를 덮지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.builder.elements import (
    UNSUPPORTED_MARKER_PREFIX,
    UnsupportedFeature,
    UnsupportedMarkCombination,
    build_unsupported_marker,
)
from mapsi.builder.header import parse_style_table
from mapsi.builder.section import build_section
from mapsi.config import load_style_map
from mapsi.parser import Block

_REPO = Path(__file__).resolve().parents[1]
_BASE_SECTION = _REPO / "samples" / "base" / "unpacked" / "Contents" / "section0.xml"
HP_NS = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"


@pytest.fixture(scope="module")
def style_map() -> dict:
    return load_style_map(_REPO / "spec" / "styles.yaml")


@pytest.fixture(scope="module")
def style_table() -> dict:
    return parse_style_table(
        (_REPO / "templates" / "Contents" / "header.xml").read_bytes()
    )


def test_exception_hierarchy() -> None:
    """UnsupportedMarkCombination ⊂ UnsupportedFeature ⊂ NotImplementedError."""
    assert issubclass(UnsupportedMarkCombination, UnsupportedFeature)
    assert issubclass(UnsupportedFeature, NotImplementedError)


def test_marker_helper_produces_본문_paragraph(style_map, style_table) -> None:
    p = build_unsupported_marker("원본 텍스트", style_map, style_table)
    assert p.tag == f"{HP_NS}p"
    assert p.get("styleIDRef") == "3"  # 본문
    t = p.find(f"{HP_NS}run/{HP_NS}t")
    assert t is not None
    assert t.text == "〔MAPSI 미처리: 원본 텍스트〕"
    assert UNSUPPORTED_MARKER_PREFIX in t.text  # 검색 접두어 포함


def _link_equation_overlap_block() -> Block:
    """링크 범위[0,8) 내부에 수식 offset 4 가 겹치는 단락 (미지원 조합)."""
    return Block(
        role="paragraph",
        text="보이는  텍스트 가 든 문단.",
        meta={
            "inline_marks": [
                {"kind": "link", "start": 0, "end": 8, "url": "http://x.com"}
            ],
            "equation_marks": [{"offset": 4, "latex": "x^2", "display": False}],
        },
    )


def test_marker_fallback_replaces_block_and_continues(
    style_map, style_table
) -> None:
    """미지원 블록은 표식 단락으로 대체되고, 앞뒤 정상 블록은 그대로 변환된다."""
    blocks = [
        Block(role="paragraph", text="앞 정상."),
        _link_equation_overlap_block(),
        Block(role="paragraph", text="뒤 정상."),
    ]
    xml = build_section(blocks, style_map, style_table, _BASE_SECTION).decode("utf-8")
    assert UNSUPPORTED_MARKER_PREFIX in xml          # 표식이 들어감
    assert "보이는  텍스트 가 든 문단." in xml         # 표식에 원문 포함
    assert "앞 정상." in xml and "뒤 정상." in xml     # 앞뒤 정상 변환


def test_real_error_propagates_not_swallowed(style_map, style_table) -> None:
    """UnsupportedFeature 가 아닌 진짜 오류(미정의 role) 는 표식으로 덮지 않고 전파."""
    blocks = [Block(role="존재하지않는역할_xyz", text="x")]
    with pytest.raises(Exception) as exc:
        build_section(blocks, style_map, style_table, _BASE_SECTION)
    # 표식 폴백이 삼키지 않았으므로 UnsupportedFeature 가 아니다
    assert not isinstance(exc.value, UnsupportedFeature)
