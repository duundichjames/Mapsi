"""``mapsi.ast_walker`` 의 단위 테스트.

본 모듈은 현재 표 캡션 승격 (ADR 0001) 만 적용한다. 후속 픽스처에서
그림 캡션 / 참고문헌 / 각주 규칙이 추가되면 케이스를 늘릴 것.
"""

from __future__ import annotations

from mapsi.ast_walker import TABLE_CAPTION_PATTERN, walk
from mapsi.parser import Block


def _table(rows: list[list[str]], caption: str | None = None) -> Block:
    return Block(role="table", meta={"rows": rows, "caption": caption})


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
