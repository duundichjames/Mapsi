"""BibTeX 파싱 — bibtexparser v1 래퍼.

bibtexparser v1 API 를 감싸고, 파일과 인라인 문자열 양쪽을 동일
인터페이스로 로드한다.

반환 형식
----------
``dict[str, dict]`` — citekey(str) → 엔트리 딕셔너리.

각 엔트리 딕셔너리는 bibtexparser v1 가 반환하는 구조 그대로이며
주요 키는 다음과 같다.

- ``ID``: citekey 문자열
- ``ENTRYTYPE``: "article", "book", "inproceedings", "misc" 등
- ``author``, ``year``, ``title``, ``journal``, ``volume``,
  ``number``, ``pages``, ``publisher``, ``address``, ...

동일 citekey 가 여러 소스에서 등장할 경우 **먼저** 정의된 항목을
채택한다 (외부 .bib 파일이 인라인보다 우선, 소스 내부에서는 위에서
아래 순).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

log = logging.getLogger(__name__)


def load_bibliography(
    bib_files: Sequence[str | Path] = (),
    inline_strings: Sequence[str] = (),
) -> dict[str, dict]:
    """BibTeX 데이터를 로드해 citekey → 엔트리 사전으로 반환한다.

    Parameters
    ----------
    bib_files:
        `.bib` 파일 경로 목록. 각 파일을 UTF-8 로 읽는다.
    inline_strings:
        마크다운 본문의 ``bibtex`` 펜스 블록에서 추출한 BibTeX 문자열 목록.

    Returns
    -------
    dict[str, dict]
        citekey(str) → bibtexparser 엔트리 dict. 소스가 없으면 빈 dict.

    Raises
    ------
    FileNotFoundError
        지정한 .bib 파일이 존재하지 않을 때.
    """
    import bibtexparser  # lazy import: bibliography 기능 미사용 시 임포트 생략
    from bibtexparser.bparser import BibTexParser

    def _make_parser() -> BibTexParser:
        p = BibTexParser(common_strings=True)
        p.ignore_nonstandard_types = False
        p.homogenize_fields = False
        return p

    db: dict[str, dict] = {}

    for path in bib_files:
        resolved = Path(path)
        if not resolved.is_file():
            raise FileNotFoundError(
                f"bibliography 파일을 찾을 수 없음: {resolved}"
            )
        content = resolved.read_text(encoding="utf-8")
        _merge_entries(bibtexparser.loads(content, _make_parser()), db)

    for content in inline_strings:
        if content.strip():
            _merge_entries(bibtexparser.loads(content, _make_parser()), db)

    return db


def _merge_entries(bib_db: object, target: dict[str, dict]) -> None:
    """bibtexparser BibDatabase 의 엔트리를 target 에 병합한다.

    이미 등록된 key 는 건너뛴다 (먼저 정의된 항목 우선).
    """
    for entry in getattr(bib_db, "entries", []):
        key = entry.get("ID")
        if not key:
            log.debug("ID 없는 BibTeX 엔트리 스킵: %r", entry)
            continue
        if key not in target:
            target[key] = dict(entry)
        else:
            log.debug("중복 citekey 스킵 (기존 항목 유지): %s", key)
