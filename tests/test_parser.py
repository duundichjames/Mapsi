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
    """수평선(``hr``) 토큰은 아직 미지원이며 명시적 에러를 내야 한다."""
    md = _write(tmp_path, "한 줄.\n\n---\n\n다른 줄.\n")
    with pytest.raises(NotImplementedError, match="hr"):
        parse_markdown(md)


def test_blockquote_single_paragraph(tmp_path: Path) -> None:
    md = _write(tmp_path, "> 인용 한 줄.\n")
    blocks = parse_markdown(md)
    assert blocks == [Block(role="blockquote", text="인용 한 줄.")]


def test_blockquote_multiple_paragraphs(tmp_path: Path) -> None:
    """인용 안의 여러 단락은 각각 blockquote 블록으로 분리된다."""
    md = _write(tmp_path, "> 첫째 단락.\n>\n> 둘째 단락.\n")
    blocks = parse_markdown(md)
    assert blocks == [
        Block(role="blockquote", text="첫째 단락."),
        Block(role="blockquote", text="둘째 단락."),
    ]


def test_blockquote_surrounded_by_paragraphs(tmp_path: Path) -> None:
    md = _write(
        tmp_path,
        "앞 단락.\n\n"
        "> 인용문.\n\n"
        "뒷 단락.\n",
    )
    blocks = parse_markdown(md)
    assert [(b.role, b.text) for b in blocks] == [
        ("paragraph", "앞 단락."),
        ("blockquote", "인용문."),
        ("paragraph", "뒷 단락."),
    ]


def test_fenced_code_block_one_line_per_block(tmp_path: Path) -> None:
    md = _write(
        tmp_path,
        "```python\n"
        "print('hello')\n"
        "print('world')\n"
        "```\n",
    )
    blocks = parse_markdown(md)
    assert [(b.role, b.text) for b in blocks] == [
        ("code_block", "print('hello')"),
        ("code_block", "print('world')"),
    ]
    assert blocks[0].meta.get("info") == "python"
    assert "info" not in blocks[1].meta


def test_fenced_code_block_with_blank_line_inside(tmp_path: Path) -> None:
    """코드 블록 안의 빈 줄도 빈 텍스트의 code_block 으로 보존된다."""
    md = _write(
        tmp_path,
        "```\n"
        "a\n"
        "\n"
        "b\n"
        "```\n",
    )
    blocks = parse_markdown(md)
    assert [(b.role, b.text) for b in blocks] == [
        ("code_block", "a"),
        ("code_block", ""),
        ("code_block", "b"),
    ]


def test_indented_code_block(tmp_path: Path) -> None:
    """4칸 들여쓰기 코드 블록도 동일하게 줄당 1 Block."""
    md = _write(tmp_path, "도입 단락.\n\n    foo()\n    bar()\n")
    blocks = parse_markdown(md)
    assert [(b.role, b.text) for b in blocks] == [
        ("paragraph", "도입 단락."),
        ("code_block", "foo()"),
        ("code_block", "bar()"),
    ]


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


def test_simple_table_emits_single_block(tmp_path: Path) -> None:
    """GFM 표 1 개는 ``role='table'`` Block 1 개로 평탄화된다."""
    md = _write(
        tmp_path,
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
        "| 3 | 4 |\n",
    )
    blocks = parse_markdown(md)
    assert len(blocks) == 1
    blk = blocks[0]
    assert blk.role == "table"
    assert blk.meta["rows"] == [["a", "b"], ["1", "2"], ["3", "4"]]
    assert blk.meta["caption"] is None  # 파서는 캡션 결정 안 함


def test_table_with_surrounding_paragraphs(tmp_path: Path) -> None:
    md = _write(
        tmp_path,
        "앞 단락.\n\n"
        "| h1 | h2 |\n"
        "|----|----|\n"
        "| x  | y  |\n\n"
        "뒷 단락.\n",
    )
    blocks = parse_markdown(md)
    roles = [b.role for b in blocks]
    assert roles == ["paragraph", "table", "paragraph"]
    assert blocks[1].meta["rows"] == [["h1", "h2"], ["x", "y"]]


def test_table_caption_is_not_promoted_by_parser(tmp_path: Path) -> None:
    """파서 단계에서는 캡션 패턴 단락이 그대로 paragraph 로 남는다.

    캡션 승격은 ``ast_walker.walk()`` 의 책임 (ADR 0001).
    """
    md = _write(
        tmp_path,
        "표 1. 분기별 매출\n\n"
        "| q | v |\n"
        "|---|---|\n"
        "| 1 | 100 |\n",
    )
    blocks = parse_markdown(md)
    assert blocks[0] == Block(role="paragraph", text="표 1. 분기별 매출")
    assert blocks[1].role == "table"
    assert blocks[1].meta["caption"] is None


def test_image_only_paragraph_emits_figure_block(tmp_path: Path) -> None:
    """``![alt](src)`` 단독 단락은 ``role='figure'`` Block 으로 변환된다."""
    md = _write(tmp_path, "![개요도](images/overview.png)\n")
    blocks = parse_markdown(md)
    assert len(blocks) == 1
    blk = blocks[0]
    assert blk.role == "figure"
    assert blk.text == "개요도"
    assert blk.meta == {"src": "images/overview.png", "caption": None}


def test_image_with_empty_alt(tmp_path: Path) -> None:
    """alt 가 비어 있어도 figure 블록은 정상 생성된다 (text 만 빈 문자열)."""
    md = _write(tmp_path, "![](images/no_alt.png)\n")
    blocks = parse_markdown(md)
    assert blocks == [
        Block(
            role="figure",
            text="",
            meta={"src": "images/no_alt.png", "caption": None},
        )
    ]


def test_image_mixed_with_text_falls_back_to_paragraph(tmp_path: Path) -> None:
    """그림과 텍스트가 한 단락에 섞여 있으면 figure 가 아닌 paragraph 로 본다.

    인라인 그림 처리는 후속 픽스처에서 별도 다룬다 (현재는 alt 텍스트조차
    평문에 포함되지 않으며, 빈 자리만 남는 것이 정상 동작).
    """
    md = _write(tmp_path, "앞 ![alt](x.png) 뒤\n")
    blocks = parse_markdown(md)
    assert len(blocks) == 1
    assert blocks[0].role == "paragraph"


def test_figure_with_surrounding_paragraphs(tmp_path: Path) -> None:
    md = _write(
        tmp_path,
        "앞 단락.\n\n"
        "![도식](pic.png)\n\n"
        "그림 1. 캡션 본문\n\n"
        "뒷 단락.\n",
    )
    blocks = parse_markdown(md)
    roles = [b.role for b in blocks]
    assert roles == ["paragraph", "figure", "paragraph", "paragraph"]
    assert blocks[1].text == "도식"
    assert blocks[1].meta["src"] == "pic.png"
    assert blocks[1].meta["caption"] is None  # 파서는 캡션 결정 안 함


def test_figure_caption_is_not_promoted_by_parser(tmp_path: Path) -> None:
    """파서 단계에서는 그림 직후 캡션 패턴 단락이 그대로 paragraph 로 남는다.

    캡션 승격은 ``ast_walker.walk()`` 의 책임 (ADR 0001 일반화 적용).
    """
    md = _write(tmp_path, "![도식](pic.png)\n\n그림 1. 본문\n")
    blocks = parse_markdown(md)
    assert blocks[0].role == "figure"
    assert blocks[0].meta["caption"] is None
    assert blocks[1] == Block(role="paragraph", text="그림 1. 본문")


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
    """``tests/golden/01_headings/input.md`` 가 의도한 9 블록을 만든다."""
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
        ("heading", 6, "제목6"),
        ("paragraph", 0, "본문으로 복귀한 단락입니다."),
    ]


# --- footnote (07_footnote) ----------------------------------------------


def test_footnote_ref_creates_inline_mark(tmp_path: Path) -> None:
    """본문 ``[^1]`` 가 paragraph 의 footnote_marks 로 보존된다.

    각주 마커 자체는 ``text`` 에 남지 않는다 (한/글이 자동번호로 표시).
    offset 은 마커 *직전까지* 누적된 평문 길이.
    """
    md = _write(tmp_path, "고향[^1]은 산골.\n\n[^1]: 본문.\n")
    blocks = parse_markdown(md)
    assert blocks[0].role == "paragraph"
    assert blocks[0].text == "고향은 산골."
    assert blocks[0].meta == {
        "footnote_marks": [
            {"kind": "footnote_ref", "offset": 2, "footnote_id": 0}
        ]
    }


def test_footnote_def_block_emitted(tmp_path: Path) -> None:
    """``[^1]: ...`` 정의 블록은 footnote_def Block 으로 emit 된다."""
    md = _write(tmp_path, "본문[^1].\n\n[^1]: 각주 본문.\n")
    blocks = parse_markdown(md)
    defs = [b for b in blocks if b.role == "footnote_def"]
    assert len(defs) == 1
    assert defs[0].text == "각주 본문."
    assert defs[0].meta == {"footnote_id": 0}


def test_footnote_id_is_assigned_by_appearance_order(tmp_path: Path) -> None:
    """원문 라벨('1', 'second') 은 무시되고 등장 순서로 0,1,... 부여."""
    md = _write(
        tmp_path,
        "A[^1].\n\nB[^second].\n\n[^1]: 일.\n\n[^second]: 이.\n",
    )
    blocks = parse_markdown(md)
    paragraphs = [b for b in blocks if b.role == "paragraph"]
    defs = [b for b in blocks if b.role == "footnote_def"]
    assert [
        m["footnote_id"] for p in paragraphs for m in p.meta.get("footnote_marks", [])
    ] == [0, 1]
    assert [d.meta["footnote_id"] for d in defs] == [0, 1]


def test_multiple_footnote_refs_in_same_paragraph(tmp_path: Path) -> None:
    """한 단락 안의 여러 각주 마커가 offset 순으로 모두 보존된다."""
    md = _write(
        tmp_path,
        "AA[^1] BB[^2] CC.\n\n[^1]: 일.\n\n[^2]: 이.\n",
    )
    blocks = parse_markdown(md)
    para = blocks[0]
    assert para.role == "paragraph"
    assert para.text == "AA BB CC."
    marks = para.meta["footnote_marks"]
    # offset: "AA"(2) → 첫 마커 → " BB"(+3=5) → 두번째 마커
    assert [m["offset"] for m in marks] == [2, 5]
    assert [m["footnote_id"] for m in marks] == [0, 1]


def test_paragraph_without_footnote_has_no_marks_meta(tmp_path: Path) -> None:
    """각주 없는 평범한 단락은 meta 에 footnote_marks 키가 추가되지 않는다."""
    md = _write(tmp_path, "그냥 본문.\n")
    blocks = parse_markdown(md)
    assert blocks == [Block(role="paragraph", text="그냥 본문.")]
    assert "footnote_marks" not in blocks[0].meta


def test_footnote_def_text_strips_outer_whitespace(tmp_path: Path) -> None:
    """정의 본문의 앞/뒤 공백·개행은 다듬는다 (저장 부담 감소)."""
    md = _write(tmp_path, "본문[^x].\n\n[^x]:    여백 포함 본문.    \n")
    blocks = parse_markdown(md)
    defs = [b for b in blocks if b.role == "footnote_def"]
    assert defs[0].text == "여백 포함 본문."


def test_round_trip_07_footnote_sample(repo_root: Path) -> None:
    """A 의 ``samples/incremental/07_footnote/07_footnote.md`` 가 4 블록.

    구성: 본문 paragraph 2 + footnote_def 2.
    각각의 인라인 마크와 정의 ID 가 등장 순서로 0, 1.
    """
    md = repo_root / "samples" / "incremental" / "07_footnote" / "07_footnote.md"
    blocks = parse_markdown(md)
    assert [(b.role, b.text) for b in blocks] == [
        ("paragraph", "나의 살던 고향은 꽃피는 산골."),
        ("paragraph", "복숭아꽃 살구꽃 아기 진달래."),
        ("footnote_def", "첫번째 각주 본문입니다."),
        (
            "footnote_def",
            "두번째 각주 본문입니다. 원문 ID 는 무시되고 등장 순서에 따라 2 번 각주가 됩니다.",
        ),
    ]
    assert blocks[0].meta["footnote_marks"] == [
        {"kind": "footnote_ref", "offset": 8, "footnote_id": 0}
    ]
    assert blocks[1].meta["footnote_marks"] == [
        {"kind": "footnote_ref", "offset": 15, "footnote_id": 1}
    ]
    assert blocks[2].meta == {"footnote_id": 0}
    assert blocks[3].meta == {"footnote_id": 1}


# ---------------------------------------------------------------------------
# Phase 9: 수식 (math_inline / math_block) 파싱
# ---------------------------------------------------------------------------


class TestInlineEquation:
    """``$...$`` 인라인 수식이 paragraph 의 ``equation_marks`` 에 보관된다."""

    def test_single_inline_equation(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "본문 $a^2 + b^2 = c^2$ 입니다.\n")
        blocks = parse_markdown(md)
        assert len(blocks) == 1
        b = blocks[0]
        assert b.role == "paragraph"
        # 마커 자체는 평문에서 제외 — 양옆 평문만 남음.
        assert b.text == "본문  입니다."
        assert b.meta["equation_marks"] == [
            {"offset": 3, "latex": "a^2 + b^2 = c^2", "display": False}
        ]
        assert "footnote_marks" not in b.meta

    def test_inline_equation_at_paragraph_start(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "$x$ 는 변수.\n")
        blocks = parse_markdown(md)
        assert blocks[0].text == " 는 변수."
        marks = blocks[0].meta["equation_marks"]
        assert marks == [{"offset": 0, "latex": "x", "display": False}]

    def test_inline_equation_at_paragraph_end(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "끝의 수식 $y$\n")
        blocks = parse_markdown(md)
        assert blocks[0].text == "끝의 수식 "
        marks = blocks[0].meta["equation_marks"]
        assert marks == [{"offset": 6, "latex": "y", "display": False}]

    def test_multiple_inline_equations_in_same_paragraph(
        self, tmp_path: Path
    ) -> None:
        md = _write(tmp_path, "값 $a$ 와 $b$ 의 합 $c$ 입니다.\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta["equation_marks"]
        assert [m["latex"] for m in marks] == ["a", "b", "c"]
        assert [m["offset"] for m in marks] == [2, 5, 10]
        assert all(m["display"] is False for m in marks)
        assert blocks[0].text == "값  와  의 합  입니다."

    def test_no_equation_means_no_equation_marks_key(
        self, tmp_path: Path
    ) -> None:
        md = _write(tmp_path, "수식 없는 평문.\n")
        blocks = parse_markdown(md)
        assert "equation_marks" not in blocks[0].meta


class TestDisplayEquation:
    """``$$...$$`` 디스플레이 수식이 단독 paragraph Block 으로 발급된다."""

    def test_single_display_equation(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "$$\n\\frac{a}{b}\n$$\n")
        blocks = parse_markdown(md)
        assert len(blocks) == 1
        b = blocks[0]
        assert b.role == "paragraph"
        assert b.text == ""
        assert b.meta["equation_marks"] == [
            {"offset": 0, "latex": "\\frac{a}{b}", "display": True}
        ]

    def test_display_between_paragraphs(self, tmp_path: Path) -> None:
        md = _write(
            tmp_path,
            "앞 단락.\n\n$$\nE = mc^2\n$$\n\n뒤 단락.\n",
        )
        blocks = parse_markdown(md)
        assert [b.role for b in blocks] == ["paragraph"] * 3
        assert blocks[0].text == "앞 단락."
        assert blocks[1].text == ""
        assert blocks[1].meta["equation_marks"] == [
            {"offset": 0, "latex": "E = mc^2", "display": True}
        ]
        assert blocks[2].text == "뒤 단락."
        # 평문 단락에는 equation_marks 가 없어야.
        assert "equation_marks" not in blocks[0].meta
        assert "equation_marks" not in blocks[2].meta

    def test_round_trip_09_equations_sample(self, repo_root: Path) -> None:
        """A 의 ``samples/incremental/09_equations/09_equations.md`` 정상 파싱.

        구성 (마크다운 본문 단락 4개 = paragraph 4): 본문(인라인 수식 1) +
        본문 + 디스플레이 수식 단독 + 본문.
        """
        md = (
            repo_root
            / "samples"
            / "incremental"
            / "09_equations"
            / "09_equations.md"
        )
        blocks = parse_markdown(md)
        roles = [b.role for b in blocks]
        assert roles == ["paragraph"] * 4
        # 1번 단락: 인라인 수식
        assert "equation_marks" in blocks[0].meta
        assert blocks[0].meta["equation_marks"][0]["display"] is False
        # 3번 단락: 디스플레이 수식
        assert blocks[2].text == ""
        eq2 = blocks[2].meta["equation_marks"]
        assert len(eq2) == 1 and eq2[0]["display"] is True


# --- inline 서식 (Phase 10, ADR 0004) -------------------------------------


class TestInlineFormattingMarks:
    """``**bold**``, ``*em*``, ``~~s~~``, ``` `code` ``, ``[]()`` 의 파싱."""

    def test_bold_creates_inline_mark(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "안녕 **굵은** 텍스트.\n")
        b = parse_markdown(md)[0]
        assert b.text == "안녕 굵은 텍스트."
        assert b.meta["inline_marks"] == [
            {"kind": "bold", "start": 3, "end": 5}
        ]

    def test_italic_creates_inline_mark(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "*기울인* 텍스트.\n")
        b = parse_markdown(md)[0]
        assert b.text == "기울인 텍스트."
        assert b.meta["inline_marks"] == [
            {"kind": "italic", "start": 0, "end": 3}
        ]

    def test_strikethrough_creates_inline_mark(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "~~취소~~ 됐다.\n")
        b = parse_markdown(md)[0]
        assert b.text == "취소 됐다."
        assert b.meta["inline_marks"] == [
            {"kind": "strike", "start": 0, "end": 2}
        ]

    def test_inline_code_absorbs_content_into_text(self, tmp_path: Path) -> None:
        """`code` 의 내용은 평문에 흡수되고, 그 범위가 mark 로 기록."""
        md = _write(tmp_path, "함수 `foo()` 호출.\n")
        b = parse_markdown(md)[0]
        assert b.text == "함수 foo() 호출."
        assert b.meta["inline_marks"] == [
            {"kind": "code", "start": 3, "end": 8}
        ]

    def test_link_label_kept_url_dropped(self, tmp_path: Path) -> None:
        """ADR 0004 결정 1: 라벨만 평문에 들어가고 URL 은 폐기, mark 도 없음."""
        md = _write(tmp_path, "[GitHub](https://github.com) 링크.\n")
        b = parse_markdown(md)[0]
        assert b.text == "GitHub 링크."
        assert "inline_marks" not in b.meta

    def test_nested_bold_italic_emits_two_marks(self, tmp_path: Path) -> None:
        """``***x***`` 는 bold 와 italic 두 mark 가 동일 범위로 등장."""
        md = _write(tmp_path, "***굵고기울어*** 끝.\n")
        b = parse_markdown(md)[0]
        assert b.text == "굵고기울어 끝."
        marks = sorted(b.meta["inline_marks"], key=lambda m: m["kind"])
        assert marks == [
            {"kind": "bold",   "start": 0, "end": 5},
            {"kind": "italic", "start": 0, "end": 5},
        ]

    def test_multiple_marks_same_paragraph(self, tmp_path: Path) -> None:
        """한 단락에 4종이 다 등장. text 의 offset 들이 정확."""
        md = _write(tmp_path, "**B** *I* ~~S~~ `C`\n")
        b = parse_markdown(md)[0]
        assert b.text == "B I S C"
        kinds = {m["kind"] for m in b.meta["inline_marks"]}
        assert kinds == {"bold", "italic", "strike", "code"}

    def test_no_inline_marks_means_no_meta_key(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "그냥 평문.\n")
        b = parse_markdown(md)[0]
        assert "inline_marks" not in b.meta

    def test_empty_label_link_yields_empty_text_no_mark(
        self, tmp_path: Path
    ) -> None:
        md = _write(tmp_path, "X[](https://x) Y.\n")
        b = parse_markdown(md)[0]
        assert b.text == "X Y."
        assert "inline_marks" not in b.meta


class TestListItemInlineMarks:
    """리스트 항목 (bullet/ordered) 안의 인라인 서식도 paragraph 와
    동일하게 ``meta["inline_marks"]`` 로 보존되는지.

    Phase 11 CP4 통합 골든이 노출시킨 회귀 — Phase 10 작업이 paragraph
    경로만 ``_inline_to_text_and_marks`` 를 사용하고 list_item 경로는
    ``_inline_to_text`` (마크 폐기) 만 사용했었다. 이 테스트들은 그
    누락이 다시 들어오지 않도록 잠근다.
    """

    def test_bullet_item_bold_creates_inline_mark(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "- **첫째** 항목\n- **둘째** 항목\n")
        blocks = parse_markdown(md)
        assert [(b.role, b.text) for b in blocks] == [
            ("bullet_list", "첫째 항목"),
            ("bullet_list", "둘째 항목"),
        ]
        assert blocks[0].meta["inline_marks"] == [
            {"kind": "bold", "start": 0, "end": 2}
        ]
        assert blocks[1].meta["inline_marks"] == [
            {"kind": "bold", "start": 0, "end": 2}
        ]

    def test_ordered_item_italic_and_code_marks(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "1. *기울인* `func()` 호출\n")
        blk = parse_markdown(md)[0]
        assert blk.role == "ordered_list"
        assert blk.text == "기울인 func() 호출"
        kinds = sorted(m["kind"] for m in blk.meta["inline_marks"])
        assert kinds == ["code", "italic"]

    def test_ordered_item_link_label_kept_url_dropped(
        self, tmp_path: Path
    ) -> None:
        """ADR 0004 결정 1 이 list 경로에서도 동일 적용."""
        md = _write(tmp_path, "1. [한컴](https://hancom.com) 사이트\n")
        blk = parse_markdown(md)[0]
        assert blk.role == "ordered_list"
        assert blk.text == "한컴 사이트"
        assert "inline_marks" not in blk.meta

    def test_nested_bullet_inherits_inline_marks(self, tmp_path: Path) -> None:
        """깊이 2 의 항목도 동일하게 inline_marks 를 보존."""
        md = _write(
            tmp_path,
            "- 1단계 평문\n"
            "  - 2단계 **굵게**\n",
        )
        blocks = parse_markdown(md)
        assert [(b.role, b.depth, b.text) for b in blocks] == [
            ("bullet_list", 1, "1단계 평문"),
            ("bullet_list", 2, "2단계 굵게"),
        ]
        assert "inline_marks" not in blocks[0].meta
        assert blocks[1].meta["inline_marks"] == [
            {"kind": "bold", "start": 4, "end": 6}
        ]

    def test_plain_list_item_has_no_inline_marks_key(
        self, tmp_path: Path
    ) -> None:
        """인라인 서식 없는 list 항목은 meta 에 inline_marks 키가 없음."""
        md = _write(tmp_path, "- 그냥 평문 항목\n")
        blk = parse_markdown(md)[0]
        assert blk.role == "bullet_list"
        assert "inline_marks" not in blk.meta


class TestBlockquoteInlineMarks:
    """blockquote 안의 인라인 서식·각주·인라인 수식이 paragraph / list_item
    과 동일하게 ``meta`` 에 보존되는지.

    Phase 11 CP4 통합 골든을 인용문/코드 블록까지 확장하면서 발견된 회귀 —
    ``parser.py`` 의 ``blockquote_depth > 0`` 분기가 ``Block`` 을 만들 때
    ``text`` 만 사용하고 ``footnote_marks/equation_marks/inline_marks`` 를
    조용히 폐기하고 있었다. list_item 누락과 동일한 패턴이며, 같은 회귀가
    재발하지 않도록 잠근다.
    """

    def test_blockquote_bold_creates_inline_mark(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "> **첫째** 인용\n")
        blk = parse_markdown(md)[0]
        assert blk.role == "blockquote"
        assert blk.text == "첫째 인용"
        assert blk.meta["inline_marks"] == [
            {"kind": "bold", "start": 0, "end": 2}
        ]

    def test_blockquote_italic_and_code_marks(self, tmp_path: Path) -> None:
        md = _write(tmp_path, "> *기울인* `func()` 를 호출\n")
        blk = parse_markdown(md)[0]
        assert blk.role == "blockquote"
        assert blk.text == "기울인 func() 를 호출"
        kinds = sorted(m["kind"] for m in blk.meta["inline_marks"])
        assert kinds == ["code", "italic"]

    def test_blockquote_link_label_kept_url_dropped(
        self, tmp_path: Path
    ) -> None:
        """ADR 0004 결정 1 이 blockquote 경로에서도 동일 적용."""
        md = _write(tmp_path, "> [한컴](https://hancom.com) 출처\n")
        blk = parse_markdown(md)[0]
        assert blk.role == "blockquote"
        assert blk.text == "한컴 출처"
        assert "inline_marks" not in blk.meta

    def test_blockquote_footnote_mark_is_kept(self, tmp_path: Path) -> None:
        """blockquote 안의 각주 참조도 footnote_marks 로 보존돼야 한다."""
        md = _write(
            tmp_path,
            "> 인용문에 각주가 붙는다[^q].\n"
            "\n"
            "[^q]: 이것이 인용문 각주의 본문이다.\n",
        )
        blocks = parse_markdown(md)
        bq = next(b for b in blocks if b.role == "blockquote")
        assert bq.text == "인용문에 각주가 붙는다."
        assert "footnote_marks" in bq.meta
        assert len(bq.meta["footnote_marks"]) == 1
        mark = bq.meta["footnote_marks"][0]
        assert mark["kind"] == "footnote_ref"
        assert isinstance(mark["footnote_id"], int)

    def test_plain_blockquote_has_no_marks_keys(self, tmp_path: Path) -> None:
        """인라인 서식·각주·수식이 없는 인용문은 meta 가 비어 있어야 한다."""
        md = _write(tmp_path, "> 그냥 평문 인용\n")
        blk = parse_markdown(md)[0]
        assert blk.role == "blockquote"
        assert blk.text == "그냥 평문 인용"
        assert blk.meta == {} or blk.meta is None
