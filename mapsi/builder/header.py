"""header.xml 로더 + 스타일 테이블 파서.

``templates/Contents/header.xml`` 은 모든 스타일 정의가 누적된 마스터 헤더이며,
변환기는 이 파일을 동적으로 조립하지 않는다 (개발자 핸드오프 §3.1 의
"header.xml 의 불변성"). 본 모듈은 다음 두 가지를 담당한다.

- :func:`load_header` -- 파일을 바이트 그대로 읽어 반환
- :func:`parse_style_table` -- ``hh:style`` 정의에서 ``name -> StyleEntry``
  매핑을 추출. 빌더가 ``hp:p`` 의 ``styleIDRef`` / ``paraPrIDRef`` 와
  ``hp:run`` 의 ``charPrIDRef`` 를 결정할 때 사용.

이름이 진실원이 되는 이유는 ``mapsi.styles`` 의 설계 노트 참조.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree


__all__ = ["StyleEntry", "load_header", "parse_style_table"]


HWPML_HEAD_NS = "http://www.hancom.co.kr/hwpml/2011/head"


@dataclass(frozen=True)
class StyleEntry:
    """``hh:style`` 1 개에서 빌더가 필요로 하는 속성만 발췌."""

    id: str
    name: str
    para_pr_id: str
    char_pr_id: str


def load_header(template_path: str | Path) -> bytes:
    """header.xml 을 바이트로 읽어 그대로 반환한다.

    인코딩 변환이나 정규화를 수행하지 않는다 (lxml 의 C14N 비교 시
    원본 바이트 보존이 유리하기 때문).
    """
    return Path(template_path).read_bytes()


def parse_style_table(header_bytes: bytes) -> dict[str, StyleEntry]:
    """``header.xml`` 의 ``hh:style`` 들을 ``name -> StyleEntry`` 로 변환한다.

    Parameters
    ----------
    header_bytes:
        ``Contents/header.xml`` 의 raw 바이트.

    Returns
    -------
    dict[str, StyleEntry]
        키는 ``hh:style/@name`` 문자열 (예: ``"개요 1"``).
        각 ``StyleEntry`` 는 ``id``, ``name``, ``para_pr_id``,
        ``char_pr_id`` 를 담는다.

    Raises
    ------
    ValueError
        같은 이름의 스타일이 여러 번 등장할 때 (header.xml 정합성 오류).

    Notes
    -----
    paraPrIDRef / charPrIDRef 가 누락된 스타일은 결과에서 제외한다
    (본문 본 변환에 무관한 char/border 전용 스타일일 수 있음).
    """
    root = etree.fromstring(header_bytes)
    table: dict[str, StyleEntry] = {}
    for style in root.iter(f"{{{HWPML_HEAD_NS}}}style"):
        sid = style.get("id")
        name = style.get("name")
        para_pr_id = style.get("paraPrIDRef")
        char_pr_id = style.get("charPrIDRef")
        if sid is None or name is None:
            continue
        if para_pr_id is None or char_pr_id is None:
            continue
        if name in table:
            raise ValueError(
                f"header.xml 에 같은 이름의 스타일이 중복: {name!r} "
                f"(id={table[name].id} 와 id={sid})"
            )
        table[name] = StyleEntry(
            id=sid, name=name, para_pr_id=para_pr_id, char_pr_id=char_pr_id
        )
    return table
