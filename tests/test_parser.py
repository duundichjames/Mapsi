"""``mapsi.parser.parse_markdown`` 의 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.parser import Block, parse_markdown


def _write(tmp: Path, content: str) -> Path:
    path = tmp / "input.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_empty_markdown_returns_empty_list(tmp_path: Path) -> None:
    md = _write(tmp_path, "")
    assert parse_markdown(md) == []


def test_single_paragraph(tmp_path: Path) -> None:
    md = _write(tmp_path, "안녕하세요.\n")
    blocks = parse_markdown(md)
    assert blocks == [Block(role="paragraph", text="안녕하세요.")]


def test_multiple_paragraphs(tmp_path: Path) -> None:
    md = _write(tmp_path, "첫 단락.\n\n둘째 단락.\n\n셋째.\n")
    blocks = parse_markdown(md)
    assert [b.role for b in blocks] == ["paragraph"] * 3
    assert [b.text for b in blocks] == ["첫 단락.", "둘째 단락.", "셋째."]


@pytest.mark.parametrize(
    "marker,expected_depth",
    [("#", 1), ("##", 2), ("###", 3), ("####", 4), ("#####", 5), ("######", 6)],
)
def test_heading_levels(tmp_path: Path, marker: str, expected_depth: int) -> None:
    md = _write(tmp_path, f"{marker} 제목 텍스트\n")
    blocks = parse_markdown(md)
    assert blocks == [
        Block(role="heading", depth=expected_depth, text="제목 텍스트")
    ]


def test_heading_and_paragraph_mix(tmp_path: Path) -> None:
    content = (
        "본문 단락입니다.\n\n"
        "# 제목1\n\n"
        "## 제목2\n\n"
        "본문으로 복귀.\n"
    )
    md = _write(tmp_path, content)
    blocks = parse_markdown(md)
    assert [(b.role, b.depth, b.text) for b in blocks] == [
        ("paragraph", 0, "본문 단락입니다."),
        ("heading", 1, "제목1"),
        ("heading", 2, "제목2"),
        ("paragraph", 0, "본문으로 복귀."),
    ]


def test_yaml_front_matter_is_stripped(tmp_path: Path) -> None:
    content = (
        "---\n"
        "샘플명: test\n"
        "키: 값\n"
        "---\n"
        "\n"
        "본문.\n"
    )
    md = _write(tmp_path, content)
    blocks = parse_markdown(md)
    assert blocks == [Block(role="paragraph", text="본문.")]


def test_no_front_matter_keeps_first_line(tmp_path: Path) -> None:
    content = "첫 줄.\n\n둘째.\n"
    md = _write(tmp_path, content)
    blocks = parse_markdown(md)
    assert [b.text for b in blocks] == ["첫 줄.", "둘째."]


def test_unsupported_token_raises_not_implemented(tmp_path: Path) -> None:
    md = _write(tmp_path, "> 인용 단락\n")
    with pytest.raises(NotImplementedError, match="blockquote_open"):
        parse_markdown(md)


def test_bullet_list_single_level(tmp_path: Path) -> None:
    md = _write(tmp_path, "- 첫 항목\n- 둘째 항목\n")
    blocks = parse_markdown(md)
    assert blocks == [
        Block(role="bullet_list", depth=1, text="첫 항목"),
        Block(role="bullet_list", depth=1, text="둘째 항목"),
    ]


def test_bullet_list_nested_three_levels(tmp_path: Path) -> None:
    md = _write(
        tmp_path,
        "- A\n"
        "  - B\n"
        "    - C\n"
        "- D\n",
    )
    blocks = parse_markdown(md)
    assert [(b.role, b.depth, b.text) for b in blocks] == [
        ("bullet_list", 1, "A"),
        ("bullet_list", 2, "B"),
        ("bullet_list", 3, "C"),
        ("bullet_list", 1, "D"),
    ]


def test_bullet_list_with_surrounding_paragraphs(tmp_path: Path) -> None:
    md = _write(
        tmp_path,
        "앞 단락.\n\n"
        "- 항목1\n"
        "- 항목2\n\n"
        "뒷 단락.\n",
    )
    blocks = parse_markdown(md)
    assert [(b.role, b.depth, b.text) for b in blocks] == [
        ("paragraph", 0, "앞 단락."),
        ("bullet_list", 1, "항목1"),
        ("bullet_list", 1, "항목2"),
        ("paragraph", 0, "뒷 단락."),
    ]


def test_ordered_list_emits_ordered_role(tmp_path: Path) -> None:
    md = _write(tmp_path, "1. 첫째\n2. 둘째\n")
    blocks = parse_markdown(md)
    assert blocks == [
        Block(role="ordered_list", depth=1, text="첫째"),
        Block(role="ordered_list", depth=1, text="둘째"),
    ]


def test_round_trip_02_bullet_list_fixture(repo_root: Path) -> None:
    """``tests/golden/02_bullet_list/input.md`` 가 의도한 6 블록을 만든다."""
    md = repo_root / "tests" / "golden" / "02_bullet_list" / "input.md"
    blocks = parse_markdown(md)
    assert [(b.role, b.depth, b.text) for b in blocks] == [
        ("paragraph", 0, "목록 앞의 평문 단락입니다."),
        ("bullet_list", 1, "나의 살던 고향은 꽃피는 산골"),
        ("bullet_list", 2, "복숭아꽃 살구꽃 아기 진달래"),
        ("bullet_list", 3, "울긋불긋 꽃대궐 차리인 동네"),
        ("bullet_list", 1, "두번째 최상위 항목"),
        ("paragraph", 0, "목록 뒤의 평문 단락입니다."),
    ]


def test_softbreak_becomes_newline(tmp_path: Path) -> None:
    md = _write(tmp_path, "줄1\n줄2\n")
    blocks = parse_markdown(md)
    assert blocks == [Block(role="paragraph", text="줄1\n줄2")]


def test_round_trip_01_headings_fixture(repo_root: Path) -> None:
    """``tests/golden/01_headings/input.md`` 가 의도한 8 블록을 만든다."""
    md = repo_root / "tests" / "golden" / "01_headings" / "input.md"
    blocks = parse_markdown(md)
    assert [(b.role, b.depth, b.text) for b in blocks] == [
        ("paragraph", 0, "본문 단락입니다."),
        ("heading", 1, "제목1"),
        ("heading", 1, "제목1"),
        ("heading", 2, "제목2"),
        ("heading", 3, "제목3"),
        ("heading", 4, "제목4"),
        ("heading", 5, "제목5"),
        ("paragraph", 0, "본문으로 복귀한 단락입니다."),
    ]
