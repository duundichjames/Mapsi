"""``mapsi.builder.header`` 의 단위 테스트."""

from __future__ import annotations

from pathlib import Path

from mapsi.builder.header import StyleEntry, load_header, parse_style_table


def test_load_header_returns_bytes(templates_dir: Path) -> None:
    data = load_header(templates_dir / "Contents" / "header.xml")
    assert isinstance(data, bytes)
    assert data.startswith(b"<?xml")


def test_parse_style_table_returns_dict(templates_dir: Path) -> None:
    data = load_header(templates_dir / "Contents" / "header.xml")
    table = parse_style_table(data)
    assert len(table) > 0
    for sid, entry in table.items():
        assert isinstance(sid, str)
        assert isinstance(entry, StyleEntry)


def test_known_styles_have_expected_pr_ids(templates_dir: Path) -> None:
    """``templates/Contents/header.xml`` (= 09_equations 기준) 의 알려진 매핑."""
    data = load_header(templates_dir / "Contents" / "header.xml")
    table = parse_style_table(data)

    expectations = {
        "0": ("바탕글", "17", "7"),
        "3": ("본문", "18", "7"),
        "4": ("개요 1", "20", "12"),
        "5": ("개요 2", "22", "13"),
        "6": ("개요 3", "23", "13"),
        "7": ("개요 4", "24", "14"),
        "17": ("개요 5", "25", "15"),
    }
    for sid, (name, ppid, cpid) in expectations.items():
        assert sid in table, f"styleID {sid} 누락"
        assert table[sid].name == name
        assert table[sid].para_pr_id == ppid
        assert table[sid].char_pr_id == cpid
