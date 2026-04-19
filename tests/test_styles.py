"""mapsi.styles 와 mapsi.config 의 단위 테스트."""

from __future__ import annotations

import pytest

from mapsi.config import load_style_map
from mapsi.styles import StyleLookupError, style_id, style_name


@pytest.fixture(scope="module")
def style_map(spec_dir):
    return load_style_map(spec_dir / "styles.yaml")


class TestLoadStyleMap:
    def test_top_level_keys_present(self, style_map):
        for role in ("paragraph", "heading", "bullet_list", "ordered_list",
                     "blockquote", "code_block", "table_cell", "table_caption",
                     "figure", "figure_caption", "footnote", "reference", "memo"):
            assert role in style_map, f"누락 역할: {role}"

    def test_nested_depth_keys_are_int(self, style_map):
        for role in ("heading", "bullet_list", "ordered_list"):
            for k in style_map[role]:
                assert isinstance(k, int), f"{role} 의 깊이 키가 정수가 아님: {k!r}"


class TestStyleId:
    @pytest.mark.parametrize("role,depth,expected_id", [
        ("paragraph", 1, 3),
        ("heading", 1, 4),
        ("heading", 2, 5),
        ("heading", 3, 6),
        ("heading", 4, 7),
        ("heading", 5, 17),
        ("heading", 6, 18),
        ("bullet_list", 1, 14),
        ("bullet_list", 2, 15),
        ("bullet_list", 3, 16),
        ("ordered_list", 1, 10),
        ("ordered_list", 2, 12),
        ("ordered_list", 3, 13),
        ("blockquote", 1, 8),
        ("code_block", 1, 9),
        ("table_cell", 1, 33),
        ("table_caption", 1, 11),
        ("figure", 1, 2),
        ("figure_caption", 1, 1),
        ("footnote", 1, 25),
        ("reference", 1, 36),
        ("memo", 1, 27),
    ])
    def test_known_mappings(self, style_map, role, depth, expected_id):
        assert style_id(style_map, role, depth) == expected_id

    def test_unknown_role_raises(self, style_map):
        with pytest.raises(StyleLookupError):
            style_id(style_map, "this_role_does_not_exist")

    def test_unknown_depth_raises(self, style_map):
        with pytest.raises(StyleLookupError):
            style_id(style_map, "heading", 99)


class TestStyleName:
    def test_heading_names(self, style_map):
        assert style_name(style_map, "heading", 1) == "개요 1"
        assert style_name(style_map, "heading", 6) == "개요 6"

    def test_paragraph_name(self, style_map):
        assert style_name(style_map, "paragraph") == "본문"
