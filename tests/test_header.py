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
    for name, entry in table.items():
        assert isinstance(name, str)
        assert isinstance(entry, StyleEntry)
        assert entry.name == name


def test_known_styles_have_expected_attrs(templates_dir: Path) -> None:
    """``templates/Contents/header.xml`` (= 09_equations 기준) 의 알려진 매핑.

    키는 스타일 이름이고, 값은 (id, paraPrIDRef, charPrIDRef) 정보를 포함.
    """
    data = load_header(templates_dir / "Contents" / "header.xml")
    table = parse_style_table(data)

    expectations = {
        "바탕글": ("0", "17", "7"),
        "본문":   ("3", "18", "7"),
        "개요 1": ("4", "20", "12"),
        "개요 2": ("5", "22", "13"),
        "개요 3": ("6", "23", "13"),
        "개요 4": ("7", "24", "14"),
        "개요 5": ("17", "25", "15"),
    }
    for name, (sid, ppid, cpid) in expectations.items():
        assert name in table, f"스타일 이름 {name!r} 누락"
        assert table[name].id == sid
        assert table[name].para_pr_id == ppid
        assert table[name].char_pr_id == cpid
