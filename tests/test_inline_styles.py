"""``mapsi.inline_styles`` 의 단위 테스트 (Phase 10).

ADR 0004 결정 3·4 의 룩업 테이블 + 디그레이드 정책을 검증한다.
"""

from __future__ import annotations

import pytest

from mapsi.inline_styles import (
    BODY_CHARPR_ID,
    INLINE_CHARPR,
    INLINE_MARK_KINDS,
    MARK_PRIORITY,
    resolve_charpr,
)


class TestInlineCharprTable:
    def test_five_entries_registered(self):
        """ADR 0004 결정 4 의 5종 등록 확인."""
        assert len(INLINE_CHARPR) == 5

    def test_all_keys_are_frozenset(self):
        for key in INLINE_CHARPR:
            assert isinstance(key, frozenset)

    def test_all_values_are_str_ids(self):
        for value in INLINE_CHARPR.values():
            assert isinstance(value, str)
            assert value.isdigit()

    def test_keys_drawn_from_known_kinds(self):
        for key in INLINE_CHARPR:
            for k in key:
                assert k in INLINE_MARK_KINDS

    def test_link_not_in_kinds(self):
        """결정 1: link 는 시각 마크가 아니므로 등재 안 됨."""
        assert "link" not in INLINE_MARK_KINDS

    def test_priority_covers_all_kinds(self):
        assert set(MARK_PRIORITY) == INLINE_MARK_KINDS


class TestResolveCharpr:
    @pytest.mark.parametrize("marks,expected", [
        ({"bold"},                     "25"),
        ({"italic"},                   "26"),
        ({"bold", "italic"},           "27"),
        ({"italic", "bold"},           "27"),
        ({"strike"},                   "28"),
        ({"code"},                     "29"),
    ])
    def test_exact_match(self, marks, expected):
        assert resolve_charpr(marks) == expected

    def test_empty_returns_body(self):
        assert resolve_charpr([]) == BODY_CHARPR_ID
        assert resolve_charpr(set()) == BODY_CHARPR_ID

    def test_unknown_kinds_silently_dropped(self):
        """알 수 없는 마크 (예: link) 는 조용히 제거되어 본문 charPr 반환."""
        assert resolve_charpr({"link"}) == BODY_CHARPR_ID
        assert resolve_charpr({"bold", "link"}) == "25"

    def test_degrade_drops_lowest_priority(self):
        """{bold, italic, strike} → {bold, italic} (=27) 로 디그레이드.

        우선순위 reverse 로 strike 가 먼저 떨어진다.
        """
        result = resolve_charpr({"bold", "italic", "strike"})
        assert result == "27"

    def test_degrade_to_single_mark(self):
        """{strike, code} → 사전에 없음 → code 떨어뜨림 → {strike}=28."""
        result = resolve_charpr({"strike", "code"})
        assert result == "28"

    def test_degrade_all_the_way_to_body(self):
        """우선순위 가장 낮은 단일 마크만 만들 수 있는 디그레이드는
        해당 ID 를 반환 (전부 떨어뜨려 빈 집합 → body) 의 경계 케이스."""
        # bold + code → 사전에 없음 → code 제거 → {bold}=25
        assert resolve_charpr({"bold", "code"}) == "25"

    def test_iterable_inputs_accepted(self):
        """list / tuple / generator 등 어떤 iterable 도 받는다."""
        assert resolve_charpr(["bold"]) == "25"
        assert resolve_charpr(("italic",)) == "26"
        assert resolve_charpr(k for k in ["bold", "italic"]) == "27"

    def test_returns_body_charpr_constant(self):
        assert BODY_CHARPR_ID == "7"
