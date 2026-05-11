"""ast_walker.py 인용 관련 규칙(5·6) 단위 테스트."""

from __future__ import annotations

import pytest

from mapsi.ast_walker import walk
from mapsi.parser import Block


def _block(role="paragraph", text="", depth=0, meta=None):
    return Block(role=role, text=text, depth=depth, meta=meta or {})


def _bib(**entries):
    return entries


_KIM2023 = {
    "ID": "kim2023", "ENTRYTYPE": "article",
    "author": "김철수", "year": "2023",
    "title": "제목", "journal": "학술지",
    "volume": "1", "number": "1", "pages": "1-10",
}

_SMITH2020 = {
    "ID": "smith2020", "ENTRYTYPE": "article",
    "author": "Smith, James", "year": "2020",
    "title": "Title", "journal": "Journal",
    "volume": "5", "number": "2", "pages": "20-30",
}


# ---------------------------------------------------------------------------
# 규칙 5: 인용 마크 해결
# ---------------------------------------------------------------------------

class TestResolveCitations:
    def test_bracketed_mark_resolved(self):
        blk = _block(
            text="Hello  world.",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 6}]},
        )
        result = walk([blk], bib_data=_bib(kim2023=_KIM2023))
        marks = result[0].meta["citation_marks"]
        assert marks[0]["formatted"] == "(김철수, 2023)"

    def test_bare_mark_resolved(self):
        blk = _block(
            text=" says so.",
            meta={"citation_marks": [{"cite_type": "bare", "raw": "@smith2020", "offset": 0}]},
        )
        result = walk([blk], bib_data=_bib(smith2020=_SMITH2020))
        marks = result[0].meta["citation_marks"]
        assert marks[0]["formatted"] == "Smith (2020)"

    def test_suppress_author_resolved(self):
        blk = _block(
            text="this result .",
            meta={"citation_marks": [{"cite_type": "suppress_author", "raw": "@kim2023", "offset": 12}]},
        )
        result = walk([blk], bib_data=_bib(kim2023=_KIM2023))
        marks = result[0].meta["citation_marks"]
        assert marks[0]["formatted"] == "(2023)"

    def test_unknown_key_gets_fallback(self):
        blk = _block(
            text="See .",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@ghost", "offset": 4}]},
        )
        result = walk([blk], bib_data={})
        marks = result[0].meta["citation_marks"]
        assert "formatted" in marks[0]
        # 알 수 없는 키는 빈 문자열이 아닌 뭔가 표시
        assert marks[0]["formatted"]

    def test_no_bib_data_passthrough(self):
        """bib_data=None 이면 citation_marks 를 수정하지 않는다."""
        blk = _block(
            text="Hello  world.",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 6}]},
        )
        result = walk([blk], bib_data=None)
        marks = result[0].meta["citation_marks"]
        assert "formatted" not in marks[0]

    def test_block_without_marks_unchanged(self):
        blk = _block(text="일반 단락입니다.")
        result = walk([blk], bib_data=_bib(kim2023=_KIM2023))
        assert result[0].text == "일반 단락입니다."
        assert not result[0].meta.get("citation_marks")

    def test_first_subsequent_appearance(self):
        """두 블록에서 같은 키 → 첫 번째는 전체, 두 번째는 축약."""
        db = {
            "lee2024": {
                "ID": "lee2024", "ENTRYTYPE": "misc",
                "author": "이영희 and 박민수 and 최지훈",
                "year": "2024", "title": "X",
            }
        }
        blk1 = _block(text=" first.", meta={"citation_marks": [
            {"cite_type": "bracketed", "raw": "@lee2024", "offset": 0}
        ]})
        blk2 = _block(text=" second.", meta={"citation_marks": [
            {"cite_type": "bracketed", "raw": "@lee2024", "offset": 0}
        ]})
        result = walk([blk1, blk2], bib_data=db)
        fmt1 = result[0].meta["citation_marks"][0]["formatted"]
        fmt2 = result[1].meta["citation_marks"][0]["formatted"]
        assert "이영희·박민수·최지훈" in fmt1   # 첫 등장 전체
        assert "이영희 외" in fmt2              # 재등장 축약


# ---------------------------------------------------------------------------
# 규칙 6: 참고문헌 목록 삽입
# ---------------------------------------------------------------------------

class TestInjectReferenceList:
    def test_inject_at_end_when_no_heading(self):
        blk = _block(
            text=" is noted.",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 0}]},
        )
        result = walk([blk], bib_data=_bib(kim2023=_KIM2023))
        roles = [b.role for b in result]
        assert "heading" in roles
        assert "reference" in roles

    def test_injected_heading_is_참고문헌(self):
        blk = _block(
            text=" is noted.",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 0}]},
        )
        result = walk([blk], bib_data=_bib(kim2023=_KIM2023))
        headings = [b for b in result if b.role == "heading" and b.depth == 1]
        assert any("참고문헌" in h.text for h in headings)

    def test_inject_after_existing_heading(self):
        cite_blk = _block(
            text=" see .",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 5}]},
        )
        ref_heading = _block(role="heading", depth=1, text="참고문헌")
        result = walk([cite_blk, ref_heading], bib_data=_bib(kim2023=_KIM2023))
        # 헤딩 바로 뒤에 reference 블록이 와야 함
        heading_idx = next(i for i, b in enumerate(result) if b.role == "heading" and "참고문헌" in b.text)
        assert result[heading_idx + 1].role == "reference"

    def test_inject_after_references_heading(self):
        cite_blk = _block(
            text="see .",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 4}]},
        )
        ref_heading = _block(role="heading", depth=1, text="References")
        result = walk([cite_blk, ref_heading], bib_data=_bib(kim2023=_KIM2023))
        heading_idx = next(i for i, b in enumerate(result) if b.role == "heading" and b.text == "References")
        assert result[heading_idx + 1].role == "reference"

    def test_inject_after_bibliography_heading(self):
        cite_blk = _block(
            text="see .",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 4}]},
        )
        bib_heading = _block(role="heading", depth=1, text="Bibliography")
        result = walk([cite_blk, bib_heading], bib_data=_bib(kim2023=_KIM2023))
        heading_idx = next(i for i, b in enumerate(result) if b.role == "heading" and b.text == "Bibliography")
        assert result[heading_idx + 1].role == "reference"

    def test_no_injection_when_no_citations(self):
        blk = _block(text="단순 단락.")
        before_count = 1
        result = walk([blk], bib_data=_bib(kim2023=_KIM2023))
        # 인용이 없으면 reference 블록 삽입 없음
        assert not any(b.role == "reference" for b in result)
        assert not any(b.role == "heading" for b in result)

    def test_reference_block_text_has_entry(self):
        blk = _block(
            text=" noted.",
            meta={"citation_marks": [{"cite_type": "bracketed", "raw": "@kim2023", "offset": 0}]},
        )
        result = walk([blk], bib_data=_bib(kim2023=_KIM2023))
        ref_blocks = [b for b in result if b.role == "reference"]
        assert len(ref_blocks) == 1
        assert "김철수" in ref_blocks[0].text
        assert "2023" in ref_blocks[0].text

    def test_injection_order_matches_citation_order(self):
        """참고문헌 목록은 인용 등장 순으로 삽입된다."""
        db = _bib(kim2023=_KIM2023, smith2020=_SMITH2020)
        blk1 = _block(text=" first.", meta={"citation_marks": [
            {"cite_type": "bracketed", "raw": "@smith2020", "offset": 0}]})
        blk2 = _block(text=" second.", meta={"citation_marks": [
            {"cite_type": "bracketed", "raw": "@kim2023", "offset": 0}]})
        result = walk([blk1, blk2], bib_data=db)
        ref_blocks = [b for b in result if b.role == "reference"]
        assert len(ref_blocks) == 2
        assert "Smith" in ref_blocks[0].text    # smith2020 먼저
        assert "김철수" in ref_blocks[1].text   # kim2023 나중

    def test_existing_reference_section_blocks_preserved(self):
        """기존 # 참고문헌 섹션의 수동 항목들도 reference 역할로 남아야 함."""
        cite_blk = _block(text=" see .", meta={"citation_marks": [
            {"cite_type": "bracketed", "raw": "@kim2023", "offset": 5}]})
        ref_heading = _block(role="heading", depth=1, text="참고문헌")
        manual_ref = _block(role="paragraph", text="Mazzucato, 2015.")
        result = walk([cite_blk, ref_heading, manual_ref], bib_data=_bib(kim2023=_KIM2023))
        # 수동 항목도 demote 규칙에 의해 reference 가 되어야 함
        ref_blocks = [b for b in result if b.role == "reference"]
        assert len(ref_blocks) >= 2  # generated + manual

    def test_no_bib_data_no_injection(self):
        blk = _block(text="[@kim2023] noted.")
        result = walk([blk], bib_data=None)
        assert not any(b.role == "reference" for b in result)
