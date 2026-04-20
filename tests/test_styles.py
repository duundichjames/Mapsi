"""mapsi.styles 와 mapsi.config 의 단위 테스트."""

from __future__ import annotations

import pytest

from mapsi.config import load_style_map
from mapsi.styles import StyleLookupError, style_name


@pytest.fixture(scope="module")
def style_map(spec_dir):
    return load_style_map(spec_dir / "styles.yaml")


class TestLoadStyleMap:
    def test_top_level_keys_present(self, style_map):
        for role in (
            "paragraph", "heading", "bullet_list", "ordered_list",
            "blockquote", "code_block", "table_cell", "table_caption",
            "figure", "figure_caption", "footnote", "reference", "memo",
        ):
            assert role in style_map, f"누락 역할: {role}"

    def test_nested_depth_keys_are_int(self, style_map):
        for role in ("heading", "bullet_list", "ordered_list"):
            for k in style_map[role]:
                assert isinstance(k, int), f"{role} 의 깊이 키가 정수가 아님: {k!r}"

    def test_simple_role_values_are_str(self, style_map):
        """단순 역할(paragraph, blockquote 등)의 값은 이름 문자열이어야 한다."""
        for role in ("paragraph", "blockquote", "code_block",
                     "figure", "figure_caption", "footnote", "memo"):
            assert isinstance(style_map[role], str), \
                f"{role} 의 값이 문자열이 아님: {style_map[role]!r}"


class TestStyleName:
    @pytest.mark.parametrize("role,depth,expected", [
        ("paragraph", 1, "본문"),
        ("heading", 1, "개요 1"),
        ("heading", 2, "개요 2"),
        ("heading", 3, "개요 3"),
        ("heading", 4, "개요 4"),
        ("heading", 5, "개요 5"),
        ("heading", 6, "개요 6"),
        ("bullet_list", 1, "네모"),
        ("bullet_list", 2, "동그라미"),
        ("bullet_list", 3, "줄"),
        ("ordered_list", 1, "번호1"),
        ("ordered_list", 2, "번호2"),
        ("ordered_list", 3, "번호3"),
        ("blockquote", 1, "인용"),
        ("code_block", 1, "코드"),
        ("table_cell", 1, "표내용"),
        ("table_caption", 1, "표캡션"),
        ("figure", 1, "그림"),
        ("figure_caption", 1, "그림캡션"),
        ("footnote", 1, "각주"),
        ("reference", 1, "참고문헌"),
        ("memo", 1, "메모"),
    ])
    def test_known_mappings(self, style_map, role, depth, expected):
        assert style_name(style_map, role, depth) == expected

    def test_unknown_role_raises(self, style_map):
        with pytest.raises(StyleLookupError):
            style_name(style_map, "this_role_does_not_exist")

    def test_unknown_depth_raises(self, style_map):
        with pytest.raises(StyleLookupError):
            style_name(style_map, "heading", 99)

    def test_paragraph_depth_is_ignored(self, style_map):
        """단순 역할은 depth 인자를 무시해야 한다."""
        assert style_name(style_map, "paragraph") == "본문"
        assert style_name(style_map, "paragraph", 5) == "본문"
