"""BibTeX 통합 테스트 — 가상 마크다운으로 end-to-end 검증."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mapsi.ast_walker import walk
from mapsi.bibliography import BibFormatter, load_bibliography
from mapsi.parser import parse_markdown, read_front_matter, read_inline_bibtex


# ---------------------------------------------------------------------------
# 픽스처: 골든 디렉터리
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).parent / "golden" / "11_bibtex"


# ---------------------------------------------------------------------------
# 골든 픽스처 파싱 + walker 통합
# ---------------------------------------------------------------------------

class TestGoldenBibtex:
    """골든 입력 파일로 전체 파이프라인을 검증한다."""

    def test_front_matter_has_bibliography(self):
        fm = read_front_matter(GOLDEN_DIR / "input.md")
        assert fm.get("bibliography") == "refs.bib"

    def test_bib_file_loaded(self):
        fm = read_front_matter(GOLDEN_DIR / "input.md")
        bib_file = GOLDEN_DIR / fm["bibliography"]
        db = load_bibliography(bib_files=[bib_file])
        assert "kim2023" in db
        assert "smith2020" in db

    def test_citation_marks_extracted(self):
        blocks = parse_markdown(GOLDEN_DIR / "input.md")
        all_marks = []
        for blk in blocks:
            all_marks.extend(blk.meta.get("citation_marks", []))
        assert len(all_marks) >= 3  # bare + bracketed + bracketed(two keys)

    def test_full_pipeline(self):
        fm = read_front_matter(GOLDEN_DIR / "input.md")
        bib_file = GOLDEN_DIR / fm["bibliography"]
        db = load_bibliography(bib_files=[bib_file])
        blocks = parse_markdown(GOLDEN_DIR / "input.md")
        walked = walk(blocks, bib_data=db)

        # 인용 마크가 resolved 되었는지 확인
        all_marks = []
        for blk in walked:
            all_marks.extend(blk.meta.get("citation_marks", []))
        for mark in all_marks:
            assert "formatted" in mark, f"mark not resolved: {mark}"

        # 참고문헌 섹션이 삽입되었는지 확인
        ref_blocks = [b for b in walked if b.role == "reference"]
        assert len(ref_blocks) >= 2  # kim2023 + smith2020

        # 한국어 항목 형식 확인
        kor_entry = next(b for b in ref_blocks if "김철수" in b.text)
        assert "2023" in kor_entry.text
        assert "한국언론학보" in kor_entry.text

        # 영문 항목 형식 확인
        eng_entry = next(b for b in ref_blocks if "Smith" in b.text)
        assert "2020" in eng_entry.text


# ---------------------------------------------------------------------------
# 인라인 bibtex 블록 통합
# ---------------------------------------------------------------------------

class TestInlineBibtexPipeline:
    def test_inline_bibtex_pipeline(self, tmp_path):
        content = (
            "# 서론\n\n"
            "이 연구는 [@kim2023] 에서 출발한다.\n\n"
            "```bibtex\n"
            "@article{kim2023,\n"
            "  author = {김철수},\n"
            "  year = {2023},\n"
            "  title = {인라인 BibTeX 테스트},\n"
            "  journal = {테스트학보},\n"
            "  volume = {1},\n"
            "  number = {1},\n"
            "  pages = {1-10}\n"
            "}\n"
            "```\n\n"
            "# 참고문헌\n"
        )
        md = tmp_path / "inline.md"
        md.write_text(content, encoding="utf-8")

        inline_bibtex = read_inline_bibtex(md)
        assert len(inline_bibtex) == 1

        db = load_bibliography(inline_strings=inline_bibtex)
        assert "kim2023" in db

        blocks = parse_markdown(md)
        # bibtex 펜스 블록이 code_block 으로 나오지 않아야
        assert not any(b.role == "code_block" for b in blocks)

        walked = walk(blocks, bib_data=db)

        # 참고문헌 섹션 헤딩 이후에 삽입되었는지
        ref_heading_idx = next(
            (i for i, b in enumerate(walked) if b.role == "heading" and "참고문헌" in b.text),
            None,
        )
        assert ref_heading_idx is not None
        ref_blocks_after_heading = [
            b for b in walked[ref_heading_idx:] if b.role == "reference"
        ]
        assert len(ref_blocks_after_heading) >= 1
        assert "김철수" in ref_blocks_after_heading[0].text


# ---------------------------------------------------------------------------
# 외부 .bib + 인라인 혼합
# ---------------------------------------------------------------------------

class TestMixedBibSources:
    def test_file_and_inline_combined(self, tmp_path):
        bib_file = tmp_path / "ext.bib"
        bib_file.write_text(
            "@article{ext2021, author={외부저자}, year={2021}, title={T}, journal={J}, volume={1}, number={1}, pages={1-5}}\n",
            encoding="utf-8",
        )
        content = (
            "---\nbibliography: ext.bib\n---\n\n"
            "외부 [@ext2021] 와 인라인 [@inline2022].\n\n"
            "```bibtex\n"
            "@article{inline2022, author={인라인저자}, year={2022}, title={T}, journal={J}, volume={2}, number={2}, pages={5-9}}\n"
            "```\n"
        )
        md = tmp_path / "mixed.md"
        md.write_text(content, encoding="utf-8")

        fm = read_front_matter(md)
        bib_files = [tmp_path / fm["bibliography"]]
        inline_bibtex = read_inline_bibtex(md)
        db = load_bibliography(bib_files=bib_files, inline_strings=inline_bibtex)

        assert "ext2021" in db
        assert "inline2022" in db

        blocks = parse_markdown(md)
        walked = walk(blocks, bib_data=db)

        ref_blocks = [b for b in walked if b.role == "reference"]
        assert len(ref_blocks) == 2


# ---------------------------------------------------------------------------
# 스타일 검증 (hwpx 빌드까지)
# ---------------------------------------------------------------------------

class TestBuildSection:
    """citation_marks 가 있는 단락이 build_section 까지 오류 없이 통과."""

    def test_citation_paragraph_builds_without_error(self):
        from mapsi.builder.elements import build_paragraph
        from mapsi.builder.header import parse_style_table
        from mapsi.config import load_style_map
        from mapsi.parser import Block

        repo_root = Path(__file__).resolve().parents[1]
        style_map = load_style_map(repo_root / "spec" / "styles.yaml")
        header_bytes = (repo_root / "templates" / "Contents" / "header.xml").read_bytes()
        style_table = parse_style_table(header_bytes)

        blk = Block(
            role="paragraph",
            text="Hello  world.",
            meta={
                "citation_marks": [
                    {
                        "cite_type": "bracketed",
                        "raw": "@kim2023",
                        "offset": 6,
                        "formatted": "(김철수, 2023)",
                    }
                ]
            },
        )
        elem = build_paragraph(blk, style_map, style_table)
        from lxml import etree
        xml_str = etree.tostring(elem, encoding="unicode")
        assert "(김철수, 2023)" in xml_str
        assert "Hello " in xml_str
        assert " world." in xml_str
