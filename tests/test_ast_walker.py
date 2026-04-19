"""``mapsi.ast_walker`` 의 단위 테스트.

다루는 규칙:
    - 규칙 1: 표 캡션 승격 (직전 단락 → ``meta["caption"]``, ADR 0001)
    - 규칙 2: 그림 캡션 승격 (직후 단락 → ``meta["caption"]``)
    - 규칙 4: 각주 본문 흡수 (footnote_def → paragraph mark["text"])

후속 픽스처에서 참고문헌 규칙이 추가되면 케이스를 늘릴 것.
"""

from __future__ import annotations

from mapsi.ast_walker import (
    FIGURE_CAPTION_PATTERN,
    TABLE_CAPTION_PATTERN,
    walk,
)
from mapsi.parser import Block


def _table(rows: list[list[str]], caption: str | None = None) -> Block:
    return Block(role="table", meta={"rows": rows, "caption": caption})


def _figure(src: str, alt: str = "", caption: str | None = None) -> Block:
    return Block(role="figure", text=alt, meta={"src": src, "caption": caption})


# ---------------------------------------------------------------------------
# 정규식 자체
# ---------------------------------------------------------------------------


class TestCaptionPattern:
    def test_korean_match(self) -> None:
        m = TABLE_CAPTION_PATTERN.match("표 1. 분기별 매출")
        assert m is not None
        assert m.end() == len("표 1. ")

    def test_english_match(self) -> None:
        m = TABLE_CAPTION_PATTERN.match("Table 12. Quarterly Revenue")
        assert m is not None

    def test_multi_digit(self) -> None:
        assert TABLE_CAPTION_PATTERN.match("표 999. 큰 번호") is not None

    def test_no_period_does_not_match(self) -> None:
        assert TABLE_CAPTION_PATTERN.match("표 1 분기별") is None

    def test_no_space_after_keyword_does_not_match(self) -> None:
        assert TABLE_CAPTION_PATTERN.match("표1. 매출") is None

    def test_lowercase_table_does_not_match(self) -> None:
        """A 명세는 대문자 ``Table`` 만 인정한다."""
        assert TABLE_CAPTION_PATTERN.match("table 1. revenue") is None

    def test_does_not_match_in_middle(self) -> None:
        assert TABLE_CAPTION_PATTERN.match("앞문 표 1. 뒤") is None


# ---------------------------------------------------------------------------
# walk() 의 캡션 승격 동작
# ---------------------------------------------------------------------------


class TestCaptionPromotion:
    def test_preceding_paragraph_is_absorbed(self) -> None:
        blocks = [
            Block(role="paragraph", text="표 1. 분기별 매출"),
            _table([["a", "b"], ["1", "2"]]),
        ]
        result = walk(blocks)
        assert len(result) == 1
        assert result[0].role == "table"
        assert result[0].meta["caption"] == "분기별 매출"

    def test_english_caption(self) -> None:
        blocks = [
            Block(role="paragraph", text="Table 5. Sales by Region"),
            _table([["x"]]),
        ]
        result = walk(blocks)
        assert len(result) == 1
        assert result[0].meta["caption"] == "Sales by Region"

    def test_user_provided_number_is_discarded(self) -> None:
        """사용자가 적은 번호 값(7) 은 무시되고 캡션 본문만 남는다."""
        blocks = [
            Block(role="paragraph", text="표 7. 임의 번호 캡션"),
            _table([["x"]]),
        ]
        result = walk(blocks)
        assert result[0].meta["caption"] == "임의 번호 캡션"

    def test_non_matching_paragraph_left_intact(self) -> None:
        blocks = [
            Block(role="paragraph", text="앞 단락."),
            _table([["x"]]),
        ]
        result = walk(blocks)
        assert len(result) == 2
        assert result[0].role == "paragraph"
        assert result[1].meta["caption"] is None

    def test_heading_is_not_promoted(self) -> None:
        """헤딩 직후 표는 캡션 승격 대상 아님."""
        blocks = [
            Block(role="heading", depth=2, text="표 1. 캡션처럼 보이는 헤딩"),
            _table([["x"]]),
        ]
        result = walk(blocks)
        assert len(result) == 2
        assert result[0].role == "heading"
        assert result[1].meta["caption"] is None

    def test_already_captioned_table_is_left_alone(self) -> None:
        blocks = [
            Block(role="paragraph", text="표 1. 무시될 캡션"),
            _table([["x"]], caption="이미 있음"),
        ]
        result = walk(blocks)
        # 이미 캡션이 있으니 직전 단락을 흡수하지 않는다.
        assert len(result) == 2
        assert result[0].role == "paragraph"
        assert result[1].meta["caption"] == "이미 있음"

    def test_caption_with_only_prefix_is_not_promoted(self) -> None:
        """본문 텍스트가 비면 (예: ``표 1.``) 캡션으로 보지 않는다."""
        blocks = [
            Block(role="paragraph", text="표 1."),
            _table([["x"]]),
        ]
        result = walk(blocks)
        assert len(result) == 2
        assert result[0].role == "paragraph"

    def test_table_without_preceding_block(self) -> None:
        blocks = [_table([["x"]])]
        result = walk(blocks)
        assert len(result) == 1
        assert result[0].meta["caption"] is None

    def test_input_is_not_mutated(self) -> None:
        original_table = _table([["x"]])
        blocks = [
            Block(role="paragraph", text="표 1. 캡션"),
            original_table,
        ]
        walk(blocks)
        assert original_table.meta["caption"] is None
        assert blocks[0].text == "표 1. 캡션"

    def test_multiple_tables(self) -> None:
        blocks = [
            Block(role="paragraph", text="표 1. 첫 표"),
            _table([["a"]]),
            Block(role="paragraph", text="중간 본문"),
            Block(role="paragraph", text="표 2. 둘째 표"),
            _table([["b"]]),
        ]
        result = walk(blocks)
        roles = [b.role for b in result]
        assert roles == ["table", "paragraph", "table"]
        assert result[0].meta["caption"] == "첫 표"
        assert result[2].meta["caption"] == "둘째 표"


# ---------------------------------------------------------------------------
# 그림 캡션 정규식 (FIGURE_CAPTION_PATTERN)
# ---------------------------------------------------------------------------


class TestFigureCaptionPattern:
    def test_korean_match(self) -> None:
        m = FIGURE_CAPTION_PATTERN.match("그림 1. 농림시스템 개요")
        assert m is not None
        assert m.end() == len("그림 1. ")

    def test_english_match(self) -> None:
        assert FIGURE_CAPTION_PATTERN.match("Figure 12. System Overview") is not None

    def test_multi_digit(self) -> None:
        assert FIGURE_CAPTION_PATTERN.match("그림 999. 큰 번호") is not None

    def test_no_period_does_not_match(self) -> None:
        assert FIGURE_CAPTION_PATTERN.match("그림 1 본문") is None

    def test_lowercase_figure_does_not_match(self) -> None:
        assert FIGURE_CAPTION_PATTERN.match("figure 1. body") is None

    def test_table_prefix_does_not_match_figure_pattern(self) -> None:
        """표 패턴은 그림 정규식에 매치되지 않는다 (역도 마찬가지)."""
        assert FIGURE_CAPTION_PATTERN.match("표 1. 본문") is None
        assert TABLE_CAPTION_PATTERN.match("그림 1. 본문") is None


# ---------------------------------------------------------------------------
# 그림 캡션 승격 (walk 동작)
# ---------------------------------------------------------------------------


class TestFigureCaptionPromotion:
    def test_following_paragraph_is_absorbed(self) -> None:
        blocks = [
            _figure("a.png", alt="alt"),
            Block(role="paragraph", text="그림 1. 첫 번째 캡션"),
        ]
        result = walk(blocks)
        assert len(result) == 1
        assert result[0].role == "figure"
        assert result[0].meta["caption"] == "첫 번째 캡션"
        assert result[0].meta["src"] == "a.png"
        assert result[0].text == "alt"  # alt 는 보존

    def test_english_caption(self) -> None:
        blocks = [
            _figure("b.png"),
            Block(role="paragraph", text="Figure 5. System Overview"),
        ]
        result = walk(blocks)
        assert len(result) == 1
        assert result[0].meta["caption"] == "System Overview"

    def test_user_provided_number_is_discarded(self) -> None:
        blocks = [
            _figure("c.png"),
            Block(role="paragraph", text="그림 7. 임의 번호"),
        ]
        result = walk(blocks)
        assert result[0].meta["caption"] == "임의 번호"

    def test_non_matching_paragraph_left_intact(self) -> None:
        blocks = [
            _figure("d.png"),
            Block(role="paragraph", text="그냥 단락 (캡션 아님)."),
        ]
        result = walk(blocks)
        assert len(result) == 2
        assert result[0].role == "figure"
        assert result[0].meta["caption"] is None
        assert result[1].role == "paragraph"

    def test_caption_with_only_prefix_is_not_promoted(self) -> None:
        blocks = [
            _figure("e.png"),
            Block(role="paragraph", text="그림 1."),
        ]
        result = walk(blocks)
        assert len(result) == 2
        assert result[0].meta["caption"] is None

    def test_already_captioned_figure_is_left_alone(self) -> None:
        blocks = [
            _figure("f.png", caption="이미 있음"),
            Block(role="paragraph", text="그림 1. 무시될 캡션"),
        ]
        result = walk(blocks)
        assert len(result) == 2
        assert result[0].meta["caption"] == "이미 있음"
        assert result[1].role == "paragraph"

    def test_figure_at_end_without_following_block(self) -> None:
        blocks = [_figure("g.png", alt="alt")]
        result = walk(blocks)
        assert len(result) == 1
        assert result[0].meta["caption"] is None

    def test_heading_after_figure_is_not_promoted(self) -> None:
        """그림 직후가 헤딩이면 캡션 패턴이라도 흡수하지 않는다."""
        blocks = [
            _figure("h.png"),
            Block(role="heading", depth=2, text="그림 1. 헤딩처럼"),
        ]
        result = walk(blocks)
        assert len(result) == 2
        assert result[0].meta["caption"] is None
        assert result[1].role == "heading"

    def test_input_is_not_mutated(self) -> None:
        original = _figure("i.png", alt="alt")
        blocks = [
            original,
            Block(role="paragraph", text="그림 1. 캡션"),
        ]
        walk(blocks)
        assert original.meta["caption"] is None
        assert blocks[1].text == "그림 1. 캡션"

    def test_multiple_figures(self) -> None:
        blocks = [
            _figure("a.png"),
            Block(role="paragraph", text="그림 1. 첫 그림"),
            Block(role="paragraph", text="중간 본문"),
            _figure("b.png"),
            Block(role="paragraph", text="그림 2. 둘째 그림"),
        ]
        result = walk(blocks)
        roles = [b.role for b in result]
        assert roles == ["figure", "paragraph", "figure"]
        assert result[0].meta["caption"] == "첫 그림"
        assert result[2].meta["caption"] == "둘째 그림"

    def test_table_caption_then_figure_caption_chain(self) -> None:
        """표/그림이 같은 walk 패스에서 모두 승격되는지 확인."""
        blocks = [
            Block(role="paragraph", text="표 1. 표 캡션"),
            _table([["x"]]),
            _figure("a.png", alt="alt"),
            Block(role="paragraph", text="그림 1. 그림 캡션"),
        ]
        result = walk(blocks)
        roles = [b.role for b in result]
        assert roles == ["table", "figure"]
        assert result[0].meta["caption"] == "표 캡션"
        assert result[1].meta["caption"] == "그림 캡션"


# ---------------------------------------------------------------------------
# 각주 본문 흡수 (규칙 4)
# ---------------------------------------------------------------------------


def _para_with_footnote(text: str, marks: list[dict]) -> Block:
    return Block(role="paragraph", text=text, meta={"footnote_marks": marks})


def _footnote_def(fid: int, text: str) -> Block:
    return Block(role="footnote_def", text=text, meta={"footnote_id": fid})


class TestFootnoteAbsorption:
    def test_def_text_merges_into_paragraph_mark(self) -> None:
        """footnote_def 의 본문이 본문 paragraph 의 마크 ``text`` 로 흡수.

        흡수 후 footnote_def Block 자체는 출력에서 제거된다.
        """
        blocks = [
            _para_with_footnote(
                "고향은 산골.",
                [{"kind": "footnote_ref", "offset": 2, "footnote_id": 0}],
            ),
            _footnote_def(0, "각주 본문."),
        ]
        result = walk(blocks)
        assert [b.role for b in result] == ["paragraph"]
        assert result[0].meta["footnote_marks"] == [
            {
                "kind": "footnote_ref",
                "offset": 2,
                "footnote_id": 0,
                "text": "각주 본문.",
            }
        ]

    def test_multiple_defs_match_by_id(self) -> None:
        """여러 정의/참조가 ``footnote_id`` 키로 정확히 매칭된다."""
        blocks = [
            _para_with_footnote(
                "AA BB CC.",
                [
                    {"kind": "footnote_ref", "offset": 2, "footnote_id": 0},
                    {"kind": "footnote_ref", "offset": 5, "footnote_id": 1},
                ],
            ),
            _footnote_def(0, "일."),
            _footnote_def(1, "이."),
        ]
        result = walk(blocks)
        assert len(result) == 1
        marks = result[0].meta["footnote_marks"]
        assert [m["text"] for m in marks] == ["일.", "이."]

    def test_unmatched_mark_gets_empty_text(self) -> None:
        """정의 없는 참조는 ``text=""`` 로 두어 빌더가 빈 각주 emit."""
        blocks = [
            _para_with_footnote(
                "고아 마크.",
                [{"kind": "footnote_ref", "offset": 5, "footnote_id": 99}],
            ),
        ]
        result = walk(blocks)
        assert result[0].meta["footnote_marks"][0]["text"] == ""

    def test_orphan_def_without_ref_is_dropped_silently(self) -> None:
        """참조 없는 정의는 출력에서 사라진다 (조용히)."""
        blocks = [
            Block(role="paragraph", text="각주 없는 본문."),
            _footnote_def(0, "참조 없는 정의."),
        ]
        result = walk(blocks)
        assert [b.role for b in result] == ["paragraph"]
        assert result[0].text == "각주 없는 본문."

    def test_paragraph_without_marks_is_passthrough(self) -> None:
        """각주 마크가 없는 단락은 변경 없이 그대로 통과 (deepcopy 회피)."""
        blocks = [
            Block(role="paragraph", text="평범한 단락."),
            _footnote_def(0, "참조 없음"),
        ]
        result = walk(blocks)
        assert result[0] is blocks[0]  # 동일 객체

    def test_first_def_wins_when_id_collides(self) -> None:
        """같은 id 의 정의가 두 번 나오면 처음 정의가 우선."""
        blocks = [
            _para_with_footnote(
                "본문.",
                [{"kind": "footnote_ref", "offset": 2, "footnote_id": 0}],
            ),
            _footnote_def(0, "처음 정의."),
            _footnote_def(0, "나중 정의."),
        ]
        result = walk(blocks)
        assert result[0].meta["footnote_marks"][0]["text"] == "처음 정의."

    def test_input_is_not_mutated(self) -> None:
        """원본 blocks 의 마크 dict 가 변경되지 않아야 한다 (순수 함수)."""
        original_mark = {
            "kind": "footnote_ref",
            "offset": 2,
            "footnote_id": 0,
        }
        blocks = [
            _para_with_footnote("AA.", [original_mark]),
            _footnote_def(0, "정의."),
        ]
        walk(blocks)
        assert "text" not in original_mark
