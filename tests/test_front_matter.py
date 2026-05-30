"""front matter 의 title/author/date 를 문서 앞머리 단락으로 출력하는 기능 검증.

제목은 ``제목 1`` 스타일, 저자·날짜는 ``본문`` 스타일에 매핑된다(가벼운 경로,
header.xml 무변경). 사용자가 명시한 값만 단락이 되며, 없는 항목은 단락을
만들지 않는다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.config import load_style_map
from mapsi.converter import md_to_hwpx
from mapsi.inspect import extract_paragraph_sequence, filter_nonempty


@pytest.fixture(scope="module")
def style_map() -> dict:
    return load_style_map("spec/styles.yaml")


def _convert_head(style_map: dict, tmp_path: Path, md_text: str) -> list[tuple[str, str]]:
    md = tmp_path / "in.md"
    md.write_text(md_text, encoding="utf-8")
    out = tmp_path / "out.hwpx"
    work = tmp_path / "work"
    work.mkdir()
    md_to_hwpx(md_path=md, output_path=out, style_map=style_map, work_dir=work)
    seq = filter_nonempty(extract_paragraph_sequence(out))
    return [(i.style_name, i.text) for i in seq]


class TestFrontMatterParagraphs:
    def test_all_three_in_order_with_styles(self, style_map, tmp_path) -> None:
        head = _convert_head(
            style_map,
            tmp_path,
            "---\ntitle: 보고서 제목\nauthor: 김철수\ndate: 2026-05-31\n---\n\n본문.\n",
        )
        assert head[:3] == [
            ("제목 1", "보고서 제목"),
            ("본문", "김철수"),
            ("본문", "2026-05-31"),
        ]
        assert head[3] == ("본문", "본문.")  # 이어서 실제 본문

    def test_author_list_joined(self, style_map, tmp_path) -> None:
        head = _convert_head(
            style_map,
            tmp_path,
            "---\ntitle: T\nauthor:\n  - 김철수\n  - Smith, James\n---\n\n본문.\n",
        )
        assert ("본문", "김철수, Smith, James") in head

    def test_title_only_no_author_date(self, style_map, tmp_path) -> None:
        head = _convert_head(
            style_map, tmp_path, "---\ntitle: 제목만\n---\n\n본문.\n"
        )
        styles = [s for s, _ in head]
        assert head[0] == ("제목 1", "제목만")
        assert styles.count("제목 1") == 1
        # 저자/날짜 단락은 생성되지 않음 → 제목 다음은 곧장 본문
        assert head[1] == ("본문", "본문.")

    def test_no_front_matter_no_extra_paragraphs(self, style_map, tmp_path) -> None:
        head = _convert_head(style_map, tmp_path, "그냥 본문만.\n")
        assert head == [("본문", "그냥 본문만.")]

    def test_date_not_autofilled_when_absent(self, style_map, tmp_path) -> None:
        head = _convert_head(
            style_map, tmp_path, "---\nauthor: 저자\n---\n\n본문.\n"
        )
        # date 키가 없으면 날짜 단락이 없어야 한다 (오늘 날짜 자동 채움 금지)
        assert head[0] == ("본문", "저자")
        assert head[1] == ("본문", "본문.")
        assert len(head) == 2

    def test_complex_front_matter_only_three_keys_used(
        self, style_map, tmp_path
    ) -> None:
        # output/classoption/header-includes 등은 무시하고 title/author/date 만 사용
        md = (
            "---\ntitle: 복잡 문서\nauthor: 단독저자\ndate: 2026-01-01\n"
            "output:\n  hwpx_document:\n    toc: true\n"
            "classoption:\n  - twocolumn\n"
            "header-includes:\n  - \\usepackage{kotex}\n---\n\n복잡 본문.\n"
        )
        head = _convert_head(style_map, tmp_path, md)
        assert head[:3] == [
            ("제목 1", "복잡 문서"),
            ("본문", "단독저자"),
            ("본문", "2026-01-01"),
        ]
        assert head[3] == ("본문", "복잡 본문.")
