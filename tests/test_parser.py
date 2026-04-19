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
    md = _write(tmp_path, "- 목록 항목\n")
    with pytest.raises(NotImplementedError, match="bullet_list_open"):
        parse_markdown(md)


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
