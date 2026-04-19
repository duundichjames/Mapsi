"""mapsi.config 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.config import load_style_map


def test_load_style_map_returns_expected_structure(spec_dir: Path) -> None:
    style_map = load_style_map(spec_dir / "styles.yaml")

    assert style_map["paragraph"] == "본문"
    assert style_map["heading"][1] == "개요 1"
    assert style_map["heading"][2] == "개요 2"
    assert style_map["bullet_list"][1] == "네모"
    assert style_map["ordered_list"][1] == "번호1"


def test_nested_depth_keys_are_int(spec_dir: Path) -> None:
    style_map = load_style_map(spec_dir / "styles.yaml")

    for role in ("heading", "bullet_list", "ordered_list"):
        for key in style_map[role]:
            assert isinstance(key, int), f"{role} 키가 int 가 아님: {key!r}"


def test_raises_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError):
        load_style_map(missing)


def test_raises_when_top_level_is_not_mapping(tmp_path: Path) -> None:
    yaml_path = tmp_path / "styles.yaml"
    yaml_path.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ValueError, match="최상위는 매핑"):
        load_style_map(yaml_path)


def test_raises_when_nested_depth_key_is_not_int(tmp_path: Path) -> None:
    yaml_path = tmp_path / "styles.yaml"
    yaml_path.write_text(
        """
paragraph: 본문
heading:
  one: 개요 1
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="하위 키는 정수"):
        load_style_map(yaml_path)


def test_raises_when_paragraph_missing(tmp_path: Path) -> None:
    yaml_path = tmp_path / "styles.yaml"
    yaml_path.write_text(
        """
heading:
  1: 개요 1
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="paragraph"):
        load_style_map(yaml_path)


def test_raises_when_yaml_is_invalid(tmp_path: Path) -> None:
    yaml_path = tmp_path / "styles.yaml"
    yaml_path.write_text("paragraph: [본문\n", encoding="utf-8")

    with pytest.raises(ValueError, match="파싱 실패"):
        load_style_map(yaml_path)
