"""mapsi.bibliography.formatter (BibFormatter) 단위 테스트."""

from __future__ import annotations

import pytest

from mapsi.bibliography.formatter import BibFormatter


def _db(**entries):
    """테스트용 미니 bib_data 구성 헬퍼."""
    return entries


# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
def kor_single():
    return _db(
        kim2023={
            "ID": "kim2023",
            "ENTRYTYPE": "article",
            "author": "김철수",
            "year": "2023",
            "title": "한국 학술지의 인용 방식",
            "journal": "한국언론학보",
            "volume": "67",
            "number": "3",
            "pages": "100-130",
        }
    )


@pytest.fixture
def eng_single():
    return _db(
        smith2020={
            "ID": "smith2020",
            "ENTRYTYPE": "article",
            "author": "Smith, James",
            "year": "2020",
            "title": "A Study of Citations",
            "journal": "Journal of Studies",
            "volume": "10",
            "number": "2",
            "pages": "1--20",
        }
    )


@pytest.fixture
def kor_multi():
    return _db(
        lee2024={
            "ID": "lee2024",
            "ENTRYTYPE": "book",
            "author": "이영희 and 박민수 and 최지훈",
            "year": "2024",
            "title": "참고문헌 연구",
            "publisher": "학술출판사",
            "address": "서울",
        }
    )


@pytest.fixture
def eng_multi():
    return _db(
        jones2019={
            "ID": "jones2019",
            "ENTRYTYPE": "book",
            "author": "Jones, Alice and Brown, Bob and White, Carol",
            "year": "2019",
            "title": "Three Authors",
            "publisher": "Academic Press",
        }
    )


# ---------------------------------------------------------------------------
# 괄호 인용 (bracketed)
# ---------------------------------------------------------------------------

class TestBracketedCitation:
    def test_korean_single_author(self, kor_single):
        fmt = BibFormatter(kor_single)
        result = fmt.format_citation("bracketed", "@kim2023")
        assert result == "(김철수, 2023)"

    def test_english_single_author(self, eng_single):
        fmt = BibFormatter(eng_single)
        result = fmt.format_citation("bracketed", "@smith2020")
        assert result == "(Smith, 2020)"

    def test_with_locator(self, kor_single):
        fmt = BibFormatter(kor_single)
        result = fmt.format_citation("bracketed", "@kim2023, p. 15")
        assert result == "(김철수, 2023, p. 15)"

    def test_multiple_keys(self, kor_single, eng_single):
        db = {**kor_single, **eng_single}
        fmt = BibFormatter(db)
        result = fmt.format_citation("bracketed", "@kim2023; @smith2020")
        assert result == "(김철수, 2023; Smith, 2020)"

    def test_unknown_key_fallback(self):
        fmt = BibFormatter({})
        result = fmt.format_citation("bracketed", "@unknown2023")
        assert "@unknown2023" in result

    def test_locator_with_semicolon_keys(self, kor_single):
        db = {
            **kor_single,
            "lee2024": {"ID": "lee2024", "ENTRYTYPE": "misc", "author": "이영희", "year": "2024", "title": "X"},
        }
        fmt = BibFormatter(db)
        result = fmt.format_citation("bracketed", "@kim2023, p. 5; @lee2024")
        assert result == "(김철수, 2023, p. 5; 이영희, 2024)"


# ---------------------------------------------------------------------------
# 텍스트 내 인용 (bare)
# ---------------------------------------------------------------------------

class TestBareCitation:
    def test_korean_no_space(self, kor_single):
        fmt = BibFormatter(kor_single)
        result = fmt.format_citation("bare", "@kim2023")
        assert result == "김철수(2023)"

    def test_english_with_space(self, eng_single):
        fmt = BibFormatter(eng_single)
        result = fmt.format_citation("bare", "@smith2020")
        assert result == "Smith (2020)"


# ---------------------------------------------------------------------------
# 저자 억제 인용 (suppress_author)
# ---------------------------------------------------------------------------

class TestSuppressAuthorCitation:
    def test_year_only(self, kor_single):
        fmt = BibFormatter(kor_single)
        result = fmt.format_citation("suppress_author", "@kim2023")
        assert result == "(2023)"

    def test_year_with_locator(self, kor_single):
        fmt = BibFormatter(kor_single)
        result = fmt.format_citation("suppress_author", "@kim2023, p. 15")
        assert result == "(2023, p. 15)"


# ---------------------------------------------------------------------------
# 복수 저자
# ---------------------------------------------------------------------------

class TestMultipleAuthors:
    def test_korean_two_authors_first_time(self, kor_single):
        db = {
            **kor_single,
            "lee2024": {"ID": "lee2024", "ENTRYTYPE": "misc",
                        "author": "이영희 and 박민수", "year": "2024", "title": "X"},
        }
        fmt = BibFormatter(db)
        result = fmt.format_citation("bracketed", "@lee2024")
        assert result == "(이영희·박민수, 2024)"

    def test_english_two_authors(self, eng_multi):
        db = {
            "jones2019": {
                "ID": "jones2019", "ENTRYTYPE": "book",
                "author": "Jones, Alice and Brown, Bob",
                "year": "2019", "title": "T", "publisher": "P",
            }
        }
        fmt = BibFormatter(db)
        result = fmt.format_citation("bracketed", "@jones2019")
        assert result == "(Jones and Brown, 2019)"

    def test_korean_three_authors_first_time(self, kor_multi):
        fmt = BibFormatter(kor_multi)
        result = fmt.format_citation("bracketed", "@lee2024")
        assert result == "(이영희·박민수·최지훈, 2024)"

    def test_korean_three_authors_subsequent(self, kor_multi):
        fmt = BibFormatter(kor_multi)
        fmt.format_citation("bracketed", "@lee2024")    # 첫 등장
        result = fmt.format_citation("bracketed", "@lee2024")  # 두 번째
        assert result == "(이영희 외, 2024)"

    def test_english_three_authors_first_time(self, eng_multi):
        fmt = BibFormatter(eng_multi)
        result = fmt.format_citation("bracketed", "@jones2019")
        assert result == "(Jones, Brown, and White, 2019)"

    def test_english_three_authors_subsequent(self, eng_multi):
        fmt = BibFormatter(eng_multi)
        fmt.format_citation("bracketed", "@jones2019")    # 첫 등장
        result = fmt.format_citation("bracketed", "@jones2019")
        assert result == "(Jones et al., 2019)"


# ---------------------------------------------------------------------------
# cited_keys 추적
# ---------------------------------------------------------------------------

class TestCitedKeys:
    def test_cited_keys_in_order(self, kor_single, eng_single):
        db = {**kor_single, **eng_single}
        fmt = BibFormatter(db)
        fmt.format_citation("bracketed", "@smith2020")
        fmt.format_citation("bracketed", "@kim2023")
        assert fmt.cited_keys() == ["smith2020", "kim2023"]

    def test_duplicate_citation_counted_once(self, kor_single):
        fmt = BibFormatter(kor_single)
        fmt.format_citation("bracketed", "@kim2023")
        fmt.format_citation("bracketed", "@kim2023")
        assert fmt.cited_keys() == ["kim2023"]


# ---------------------------------------------------------------------------
# 참고문헌 목록
# ---------------------------------------------------------------------------

class TestReferenceList:
    def test_korean_article_format(self, kor_single):
        fmt = BibFormatter(kor_single)
        fmt.format_citation("bracketed", "@kim2023")
        entries = fmt.format_reference_list()
        assert len(entries) == 1
        entry = entries[0]
        assert "김철수" in entry
        assert "2023" in entry
        assert "한국언론학보" in entry
        assert "67(3)" in entry
        assert "100-130" in entry

    def test_english_article_format(self, eng_single):
        fmt = BibFormatter(eng_single)
        fmt.format_citation("bracketed", "@smith2020")
        entries = fmt.format_reference_list()
        entry = entries[0]
        assert "Smith" in entry
        assert "2020" in entry
        assert "Journal of Studies" in entry

    def test_book_format_korean(self):
        db = {
            "lee2024": {
                "ID": "lee2024", "ENTRYTYPE": "book",
                "author": "이영희", "year": "2024", "title": "참고문헌 연구",
                "publisher": "학술출판사", "address": "서울",
            }
        }
        fmt = BibFormatter(db)
        fmt.format_citation("bracketed", "@lee2024")
        entries = fmt.format_reference_list()
        entry = entries[0]
        assert "이영희" in entry
        assert "참고문헌 연구" in entry
        assert "학술출판사" in entry

    def test_reference_list_in_citation_order(self, kor_single, eng_single):
        db = {**kor_single, **eng_single}
        fmt = BibFormatter(db)
        fmt.format_citation("bracketed", "@smith2020")
        fmt.format_citation("bracketed", "@kim2023")
        entries = fmt.format_reference_list()
        assert len(entries) == 2
        assert "Smith" in entries[0]
        assert "김철수" in entries[1]

    def test_empty_when_no_citations(self, kor_single):
        fmt = BibFormatter(kor_single)
        assert fmt.format_reference_list() == []

    def test_unknown_key_entry(self):
        fmt = BibFormatter({})
        fmt.format_citation("bracketed", "@ghost2023")
        entries = fmt.format_reference_list()
        assert len(entries) == 1
        assert "ghost2023" in entries[0]
