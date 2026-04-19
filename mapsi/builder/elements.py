"""개별 HWPX XML 요소 빌더.

각 함수는 lxml ``Element`` 를 반환한다. ``section.build_section()`` 이 본
모듈의 헬퍼들을 조립해 최종 section0.xml 을 만든다.

요소별 빌더 (모두 후속 커밋에서 구현):
    - build_paragraph: hp:p (문단)
    - build_run: hp:run (인라인 서식 그룹)
    - build_text_run: hp:run + hp:t (평문)
    - build_table: hp:tbl (표)
    - build_picture: hp:pic (그림)
    - build_footnote_ref: hp:footnoteRef (각주 참조)
    - build_equation: hp:equation (수식, equation 모듈에 위임)
"""

from __future__ import annotations

from typing import Any

from lxml import etree

from ..parser import Block


__all__ = [
    "build_paragraph",
    "build_run",
    "build_text_run",
    "build_table",
    "build_picture",
    "build_footnote_ref",
]


def build_paragraph(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """문단(hp:p) 노드를 생성한다.

    block.role 과 block.depth 로부터 styleIDRef 와 paraPrIDRef 를 결정한다.
    """
    raise NotImplementedError


def build_run(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """인라인 런(hp:run) 노드를 생성한다.

    block.children 의 인라인 노드들(굵게/기울임/링크/인라인코드 등) 을
    적절한 charPr 와 함께 펼쳐 넣는다.
    """
    raise NotImplementedError


def build_text_run(text: str, char_pr_id: int = 0) -> etree._Element:
    """평문 런(hp:run + hp:t) 을 생성한다."""
    raise NotImplementedError


def build_table(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """표(hp:tbl) 노드를 생성한다.

    셀의 폭은 페이지 폭 균등 분할로 단순화한다 (HWPUNIT).
    """
    raise NotImplementedError


def build_picture(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """그림(hp:pic) 노드를 생성한다.

    이미지 등록은 ``builder.bindata.register_image`` (C 영역) 에 위임한다.
    """
    raise NotImplementedError


def build_footnote_ref(block: Block, style_map: dict[str, Any]) -> etree._Element:
    """각주 참조(hp:footnoteRef) 노드를 생성한다."""
    raise NotImplementedError
