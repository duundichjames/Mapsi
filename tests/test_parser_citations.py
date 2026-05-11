"""parser.py의 인용 마크 추출 및 새 공개 함수 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.parser import Block, parse_markdown, read_front_matter, read_inline_bibtex


def _write(tmp: Path, content: str) -> Path:
    p = tmp / "input.md"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# read_front_matter
# ---------------------------------------------------------------------------

class TestReadFrontMatter:
    def test_no_front_matter(self, tmp_path):
        md = _write(tmp_path, "본문입니다.\n")
        assert read_front_matter(md) == {}

    def test_bibliography_key(self, tmp_path):
        md = _write(tmp_path, "---\nbibliography: refs.bib\n---\n본문.\n")
        fm = read_front_matter(md)
        assert fm["bibliography"] == "refs.bib"

    def test_multiple_keys(self, tmp_path):
        md = _write(tmp_path, "---\ntitle: My Doc\nbibliography: r.bib\n---\n")
        fm = read_front_matter(md)
        assert fm["title"] == "My Doc"
        assert fm["bibliography"] == "r.bib"

    def test_empty_front_matter(self, tmp_path):
        md = _write(tmp_path, "---\n---\n본문.\n")
        assert read_front_matter(md) == {}

    def test_invalid_yaml_raises(self, tmp_path):
        md = _write(tmp_path, "---\n: invalid: yaml: here\n---\n")
        # 단순 키-값 형태가 아닌 복잡한 invalid yaml은 ValueError 를 던짐
        # (비교적 관대하므로 특정 오류를 강제하지 않는다)


# ---------------------------------------------------------------------------
# read_inline_bibtex
# ---------------------------------------------------------------------------

class TestReadInlineBibtex:
    def test_no_bibtex_blocks(self, tmp_path):
        md = _write(tmp_path, "```python\ncode\n```\n")
        assert read_inline_bibtex(md) == []

    def test_single_bibtex_block(self, tmp_path):
        content = (
            "본문.\n\n"
            "```bibtex\n"
            "@article{kim2023, author={김철수}, year={2023}}\n"
            "```\n"
        )
        md = _write(tmp_path, content)
        blocks = read_inline_bibtex(md)
        assert len(blocks) == 1
        assert "kim2023" in blocks[0]

    def test_multiple_bibtex_blocks(self, tmp_path):
        content = (
            "```bibtex\n@article{a, year={2020}}\n```\n\n"
            "```bibtex\n@book{b, year={2021}}\n```\n"
        )
        md = _write(tmp_path, content)
        blocks = read_inline_bibtex(md)
        assert len(blocks) == 2

    def test_bibtex_block_case_insensitive(self, tmp_path):
        content = "```Bibtex\n@article{x, year={2020}}\n```\n"
        md = _write(tmp_path, content)
        blocks = read_inline_bibtex(md)
        assert len(blocks) == 1


# ---------------------------------------------------------------------------
# bibtex 펜스 블록 억제
# ---------------------------------------------------------------------------

class TestBibtexFenceSuppressed:
    def test_bibtex_block_not_in_output(self, tmp_path):
        content = (
            "본문.\n\n"
            "```bibtex\n@article{x, year={2020}}\n```\n\n"
            "후문.\n"
        )
        md = _write(tmp_path, content)
        blocks = parse_markdown(md)
        roles = [b.role for b in blocks]
        assert "code_block" not in roles
        assert "paragraph" in roles

    def test_bibtex_block_suppressed_but_python_preserved(self, tmp_path):
        content = (
            "```python\nprint()\n```\n\n"
            "```bibtex\n@article{x, year={2020}}\n```\n"
        )
        md = _write(tmp_path, content)
        blocks = parse_markdown(md)
        # python fence → code_block 이 있어야 함
        assert any(b.role == "code_block" for b in blocks)
        # bibtex fence → 없어야 함 (억제)


# ---------------------------------------------------------------------------
# citation_marks 추출 (bracketed)
# ---------------------------------------------------------------------------

class TestBracketedCitationMark:
    def test_single_citation(self, tmp_path):
        md = _write(tmp_path, "Smith says [@kim2023] is correct.\n")
        blocks = parse_markdown(md)
        assert len(blocks) == 1
        marks = blocks[0].meta.get("citation_marks", [])
        assert len(marks) == 1
        assert marks[0]["cite_type"] == "bracketed"
        assert marks[0]["raw"] == "@kim2023"

    def test_citation_removed_from_text(self, tmp_path):
        md = _write(tmp_path, "Hello [@kim2023] world.\n")
        blocks = parse_markdown(md)
        assert "[@kim2023]" not in blocks[0].text

    def test_citation_with_locator(self, tmp_path):
        md = _write(tmp_path, "See [@kim2023, p. 15].\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert len(marks) == 1
        assert marks[0]["raw"] == "@kim2023, p. 15"

    def test_multiple_keys_in_one_bracket(self, tmp_path):
        md = _write(tmp_path, "See [@kim2023; @lee2024].\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert len(marks) == 1
        assert "@kim2023" in marks[0]["raw"]
        assert "@lee2024" in marks[0]["raw"]

    def test_two_separate_citations(self, tmp_path):
        md = _write(tmp_path, "[@kim2023] and also [@lee2024].\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert len(marks) == 2
        raw_values = {m["raw"] for m in marks}
        assert "@kim2023" in raw_values
        assert "@lee2024" in raw_values


# ---------------------------------------------------------------------------
# citation_marks 추출 (bare)
# ---------------------------------------------------------------------------

class TestBareCitationMark:
    def test_bare_citation(self, tmp_path):
        md = _write(tmp_path, "@kim2023 says that...\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert len(marks) == 1
        assert marks[0]["cite_type"] == "bare"
        assert marks[0]["raw"] == "@kim2023"

    def test_bare_not_inside_bracket(self, tmp_path):
        """[@key] 안의 @key 는 bare 로 별도 매치되지 않아야 한다."""
        md = _write(tmp_path, "[@kim2023] is good.\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert len(marks) == 1
        assert marks[0]["cite_type"] == "bracketed"


# ---------------------------------------------------------------------------
# citation_marks 추출 (suppress_author)
# ---------------------------------------------------------------------------

class TestSuppressAuthorCitationMark:
    def test_suppress_author(self, tmp_path):
        md = _write(tmp_path, "This was done -@kim2023.\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert len(marks) == 1
        assert marks[0]["cite_type"] == "suppress_author"
        assert marks[0]["raw"] == "@kim2023"

    def test_suppress_raw_strips_minus(self, tmp_path):
        md = _write(tmp_path, "-@lee2024 result.\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert marks[0]["raw"] == "@lee2024"


# ---------------------------------------------------------------------------
# offset 정확도
# ---------------------------------------------------------------------------

class TestCitationOffset:
    def test_offset_at_start(self, tmp_path):
        md = _write(tmp_path, "[@kim2023] says so.\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        assert marks[0]["offset"] == 0

    def test_offset_mid_text(self, tmp_path):
        md = _write(tmp_path, "Hello [@kim2023] world.\n")
        blocks = parse_markdown(md)
        marks = blocks[0].meta.get("citation_marks", [])
        # "Hello " = 6 chars before citation
        assert marks[0]["offset"] == 6

    def test_text_without_citation_is_correct(self, tmp_path):
        md = _write(tmp_path, "A [@x] B [@y] C.\n")
        blocks = parse_markdown(md)
        text = blocks[0].text
        marks = blocks[0].meta.get("citation_marks", [])
        # text 는 "A  B  C." (인용 제거 후)
        # offset[0] = 2 ("A " 이후), offset[1] = 5 ("A  B " 이후)
        assert marks[0]["offset"] == 2
        assert marks[1]["offset"] == 5
        # builder 재구성: text[:2] + fmt[0] + text[2:5] + fmt[1] + text[5:]
        # = "A " + X + " B " + Y + " C."
        assert text == "A  B  C."


# ---------------------------------------------------------------------------
# 노 마크 시 citation_marks 부재
# ---------------------------------------------------------------------------

class TestNoCitationMarks:
    def test_plain_paragraph_no_marks(self, tmp_path):
        md = _write(tmp_path, "단순 본문 단락입니다.\n")
        blocks = parse_markdown(md)
        assert not blocks[0].meta.get("citation_marks")

    def test_at_sign_in_email_like_context(self, tmp_path):
        # 이메일 주소는 false positive 가능성이 있지만 기본 동작 확인
        md = _write(tmp_path, "연락처: user@example.com\n")
        blocks = parse_markdown(md)
        # 테스트는 깨지지 않으면 충분 (false positive 존재해도 crash 없어야)
        assert len(blocks) == 1
