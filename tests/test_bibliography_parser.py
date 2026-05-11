"""mapsi.bibliography.parser 단위 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.bibliography.parser import load_bibliography


_BIB_ARTICLE_KOR = """\
@article{kim2023,
  author = {김철수},
  year = {2023},
  title = {한국 학술지의 인용 방식},
  journal = {한국언론학보},
  volume = {67},
  number = {3},
  pages = {100-130}
}
"""

_BIB_ARTICLE_ENG = """\
@article{smith2020,
  author = {Smith, James},
  year = {2020},
  title = {A Study of Citations},
  journal = {Journal of Studies},
  volume = {10},
  number = {2},
  pages = {1--20}
}
"""

_BIB_BOOK = """\
@book{lee2024,
  author = {이영희 and 박민수},
  year = {2024},
  title = {참고문헌 연구},
  publisher = {학술출판사},
  address = {서울}
}
"""


def test_load_inline_single_entry():
    db = load_bibliography(inline_strings=[_BIB_ARTICLE_KOR])
    assert "kim2023" in db
    assert db["kim2023"]["ENTRYTYPE"] == "article"
    assert db["kim2023"]["author"] == "김철수"
    assert db["kim2023"]["year"] == "2023"


def test_load_inline_multiple_entries():
    combined = _BIB_ARTICLE_KOR + "\n" + _BIB_ARTICLE_ENG
    db = load_bibliography(inline_strings=[combined])
    assert "kim2023" in db
    assert "smith2020" in db


def test_load_multiple_inline_strings():
    db = load_bibliography(inline_strings=[_BIB_ARTICLE_KOR, _BIB_ARTICLE_ENG])
    assert "kim2023" in db
    assert "smith2020" in db


def test_load_from_file(tmp_path: Path):
    bib_file = tmp_path / "refs.bib"
    bib_file.write_text(_BIB_ARTICLE_KOR, encoding="utf-8")
    db = load_bibliography(bib_files=[bib_file])
    assert "kim2023" in db


def test_duplicate_key_first_wins():
    first = "@article{kim2023, author={first}, year={2023}}\n"
    second = "@article{kim2023, author={second}, year={2023}}\n"
    db = load_bibliography(inline_strings=[first, second])
    assert db["kim2023"]["author"] == "first"


def test_file_takes_precedence_over_inline(tmp_path: Path):
    """외부 .bib 파일이 먼저 처리되므로 인라인보다 우선."""
    bib_file = tmp_path / "refs.bib"
    bib_file.write_text("@article{kim2023, author={file}, year={2023}}\n", encoding="utf-8")
    inline = "@article{kim2023, author={inline}, year={2023}}\n"
    db = load_bibliography(bib_files=[bib_file], inline_strings=[inline])
    assert db["kim2023"]["author"] == "file"


def test_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        load_bibliography(bib_files=["/nonexistent/path.bib"])


def test_empty_sources():
    db = load_bibliography()
    assert db == {}


def test_book_entry():
    db = load_bibliography(inline_strings=[_BIB_BOOK])
    assert "lee2024" in db
    assert db["lee2024"]["ENTRYTYPE"] == "book"
    assert "이영희" in db["lee2024"]["author"]


def test_entry_preserves_all_fields():
    db = load_bibliography(inline_strings=[_BIB_ARTICLE_KOR])
    e = db["kim2023"]
    assert e["volume"] == "67"
    assert e["number"] == "3"
    assert e["pages"] == "100-130"
    assert e["journal"] == "한국언론학보"
