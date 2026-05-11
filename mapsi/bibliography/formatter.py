"""인용 포매팅 및 참고문헌 목록 생성.

``BibFormatter`` 는 ``parser.load_bibliography`` 가 반환한 citekey 사전을
받아 다음 두 가지를 수행한다.

1. ``format_citation(cite_type, raw)`` — 인용 마크를 인용 표시 문자열로 변환
   - bracketed: ``(저자, 연도)`` 또는 ``(저자, 연도, 페이지)``
   - bare:       ``저자(연도)`` (한국어) / ``저자 (연도)`` (영문)
   - suppress_author: ``(연도)``

2. ``format_reference_list()`` — 인용된 모든 citekey 의 참고문헌 항목 반환
   (인용 등장 순, 중복 제거)

저자 처리
----------
- 복수 저자 첫 등장: 전체 저자 표기
  - 한국어: "김철수·이영희·박민수"
  - 영문(2명): "Kim and Lee"
  - 영문(3명+): "Kim, Lee, and Park"
- 복수 저자 두 번째 이후: 축약
  - 한국어: "김철수 외"
  - 영문: "Kim et al."

한국어 여부 판정
----------------
author 필드 첫 번째 저자에 가나다 범위(U+AC00~U+D7A3) 문자가 포함되면
한국어로 간주한다.
"""

from __future__ import annotations

import re


__all__ = ["BibFormatter"]


def _is_korean(text: str) -> bool:
    """가나다 범위 문자가 하나라도 있으면 True."""
    return any("가" <= c <= "힣" for c in text)


def _split_authors(author_field: str) -> list[str]:
    """BibTeX author 필드를 개별 저자 문자열 리스트로 분리한다.

    BibTeX 관례: " and " (대소문자 구분 없음) 로 구분.
    """
    return [a.strip() for a in re.split(r"\s+and\s+", author_field) if a.strip()]


def _family_name(author: str) -> str:
    """저자 문자열에서 성(family name)만 추출한다.

    "Last, First" 형식이면 "Last" 를 반환.
    쉼표가 없으면 (한국어·단일 이름 등) 전체 문자열 반환.
    """
    if "," in author:
        return author.split(",", 1)[0].strip()
    return author


def _format_inline_authors(
    authors: list[str], *, is_first_time: bool
) -> str:
    """인용 본문에 들어갈 저자 표시 문자열을 만든다."""
    if not authors:
        return "?"
    family = [_family_name(a) for a in authors]
    is_kor = _is_korean(family[0])
    n = len(family)

    if n == 1:
        return family[0]

    if n == 2:
        return f"{family[0]}·{family[1]}" if is_kor else f"{family[0]} and {family[1]}"

    # 3명 이상
    if not is_first_time:
        return f"{family[0]} 외" if is_kor else f"{family[0]} et al."

    # 첫 등장: 전체 나열
    if is_kor:
        return "·".join(family)
    # 영문: "A, B, and C"
    return f"{', '.join(family[:-1])}, and {family[-1]}"


def _format_ref_authors(authors: list[str]) -> str:
    """참고문헌 목록용 전체 저자 문자열."""
    if not authors:
        return "?"
    is_kor = _is_korean(authors[0])

    if is_kor:
        return "·".join(_family_name(a) for a in authors)

    # 영문: 첫 저자는 "Last, First", 나머지는 "First Last"
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]}, and {authors[1]}"
    return f"{', '.join(authors[:-1])}, and {authors[-1]}"


def _parse_cite_keys(raw: str) -> list[tuple[str, str | None]]:
    """인용 raw 문자열 → ``[(key, locator), ...]`` 리스트.

    raw 예시:
        "@kim2023"               → [("kim2023", None)]
        "@kim2023, p. 15"        → [("kim2023", "p. 15")]
        "@kim2023; @lee2024"     → [("kim2023", None), ("lee2024", None)]
        "@kim2023, p. 5; @lee2024" → [("kim2023", "p. 5"), ("lee2024", None)]
    """
    result: list[tuple[str, str | None]] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part.startswith("@"):
            continue
        rest = part[1:]  # @ 제거
        if "," in rest:
            key_part, locator = rest.split(",", 1)
            locator_str = locator.strip() or None
            result.append((key_part.strip(), locator_str))
        else:
            result.append((rest.strip(), None))
    return result


class BibFormatter:
    """BibTeX 데이터베이스 기반 인용 포매터.

    Parameters
    ----------
    db:
        ``load_bibliography`` 반환값. citekey → 엔트리 dict.

    Notes
    -----
    단일 문서 변환 1회에 1개의 인스턴스를 사용한다.
    ``format_citation`` 호출 순서가 "첫 등장 여부" 판정에 영향을 준다.
    """

    def __init__(self, db: dict[str, dict]) -> None:
        self._db = db
        self._cited_keys: list[str] = []      # 인용 등장 순 (중복 없음)
        self._first_seen: set[str] = set()    # 첫 등장 추적

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def format_citation(self, cite_type: str, raw: str) -> str:
        """인용 마크를 표시 문자열로 변환한다.

        Parameters
        ----------
        cite_type:
            ``"bracketed"`` | ``"bare"`` | ``"suppress_author"``
        raw:
            파서가 기록한 원시 문자열.
            bracketed 이면 ``"@key"`` / ``"@key, locator"`` / ``"@a; @b"``.
            bare·suppress_author 이면 ``"@key"`` (단일 키).

        Returns
        -------
        str
            포매팅된 인용 표시 문자열.
        """
        entries = _parse_cite_keys(raw)
        if not entries:
            return f"[{raw}]"

        if cite_type == "bare":
            # 단일 키만 지원 (bare citation 은 단일 인용)
            key, locator = entries[0]
            return self._format_bare(key, locator)

        if cite_type == "suppress_author":
            key, locator = entries[0]
            return self._format_suppress(key, locator)

        # bracketed (기본): 괄호 + 세미콜론 구분
        parts = []
        for key, locator in entries:
            parts.append(self._format_one_bracketed(key, locator))
        return f"({'; '.join(parts)})"

    def cited_keys(self) -> list[str]:
        """``format_citation`` 이 호출된 키를 등장 순으로 반환한다 (중복 없음)."""
        return list(self._cited_keys)

    def format_reference_list(self) -> list[str]:
        """인용된 모든 키의 참고문헌 항목 문자열 목록을 반환한다.

        인용 등장 순. 키를 알 수 없으면 해당 항목은 ``"[unknown: key]"`` 형식.
        """
        return [self._format_entry(k) for k in self._cited_keys]

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _register(self, key: str) -> bool:
        """key 를 등장 목록에 등록하고 첫 등장 여부를 반환한다."""
        is_first = key not in self._first_seen
        if is_first:
            self._first_seen.add(key)
        if key not in self._cited_keys:
            self._cited_keys.append(key)
        return is_first

    def _format_bare(self, key: str, locator: str | None) -> str:
        """bare 인용: ``저자(연도)`` 또는 ``저자 (연도)``."""
        is_first = self._register(key)
        if key not in self._db:
            return f"@{key}"
        entry = self._db[key]
        author_str = _format_inline_authors(
            _split_authors(entry.get("author", key)),
            is_first_time=is_first,
        )
        year = entry.get("year", "n.d.")
        if _is_korean(author_str):
            base = f"{author_str}({year})"
        else:
            base = f"{author_str} ({year})"
        if locator:
            base += f", {locator}"
        return base

    def _format_suppress(self, key: str, locator: str | None) -> str:
        """suppress_author 인용: ``(연도)``."""
        self._register(key)
        if key not in self._db:
            return f"(@{key})"
        entry = self._db[key]
        year = entry.get("year", "n.d.")
        inner = year + (f", {locator}" if locator else "")
        return f"({inner})"

    def _format_one_bracketed(self, key: str, locator: str | None) -> str:
        """괄호 인용에서 키 하나 분의 내용: ``저자, 연도`` 또는 ``저자, 연도, 페이지``."""
        is_first = self._register(key)
        if key not in self._db:
            return f"@{key}"
        entry = self._db[key]
        author_str = _format_inline_authors(
            _split_authors(entry.get("author", key)),
            is_first_time=is_first,
        )
        year = entry.get("year", "n.d.")
        parts = [author_str, year]
        if locator:
            parts.append(locator)
        return ", ".join(parts)

    def _format_entry(self, key: str) -> str:
        """참고문헌 목록용 단일 항목 문자열."""
        if key not in self._db:
            return f"[unknown: {key}]"
        entry = self._db[key]
        etype = entry.get("ENTRYTYPE", "misc").lower()

        authors = _split_authors(entry.get("author", ""))
        author_str = _format_ref_authors(authors)
        year = entry.get("year", "n.d.")
        title = entry.get("title", "")
        is_kor = _is_korean(author_str) if author_str != "?" else False

        if etype == "article":
            return self._format_article(author_str, year, title, entry, is_kor)
        if etype == "book":
            return self._format_book(author_str, year, title, entry, is_kor)
        if etype in ("inproceedings", "conference"):
            return self._format_inproceedings(author_str, year, title, entry, is_kor)
        # misc / 기타
        return self._format_misc(author_str, year, title, is_kor)

    @staticmethod
    def _format_article(
        author: str, year: str, title: str, entry: dict, is_kor: bool
    ) -> str:
        journal = entry.get("journal", "")
        volume = entry.get("volume", "")
        number = entry.get("number", "")
        pages = entry.get("pages", "").replace("--", "-")

        vol_info = f"{volume}({number})" if number else volume
        if is_kor:
            page_info = f", {pages}" if pages else ""
            return f"{author}. ({year}). {title}. {journal}, {vol_info}{page_info}."
        else:
            page_info = f": {pages}" if pages else ""
            return f'{author}. {year}. "{title}." {journal} {vol_info}{page_info}.'

    @staticmethod
    def _format_book(
        author: str, year: str, title: str, entry: dict, is_kor: bool
    ) -> str:
        publisher = entry.get("publisher", "")
        address = entry.get("address", "")
        pub_info = f"{address}: {publisher}" if address and publisher else publisher or address
        if is_kor:
            return f"{author}. ({year}). {title}. {pub_info}."
        else:
            return f"{author}. {year}. {title}. {pub_info}."

    @staticmethod
    def _format_inproceedings(
        author: str, year: str, title: str, entry: dict, is_kor: bool
    ) -> str:
        booktitle = entry.get("booktitle", "")
        pages = entry.get("pages", "").replace("--", "-")
        page_info = f", {pages}" if pages else ""
        if is_kor:
            return f"{author}. ({year}). {title}. {booktitle}{page_info}."
        else:
            return f'{author}. {year}. "{title}." {booktitle}{page_info}.'

    @staticmethod
    def _format_misc(author: str, year: str, title: str, is_kor: bool) -> str:
        if is_kor:
            return f"{author}. ({year}). {title}."
        else:
            return f"{author}. {year}. {title}."
