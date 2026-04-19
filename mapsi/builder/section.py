"""section0.xml 빌더.

Block 트리(walker 통과본) 와 스타일 맵을 받아 완성된 ``section0.xml`` 문자열을
반환한다. 본 모듈은 빌더의 외부 진입점이며, 개별 요소(문단/표/그림/각주/수식)
의 XML 노드 생성은 ``elements`` 모듈의 헬퍼들을 조립해 수행한다.
"""

from __future__ import annotations

from typing import Any

from ..parser import Block


__all__ = ["build_section"]


def build_section(blocks: list[Block], style_map: dict[str, Any]) -> str:
    """Block 리스트를 받아 완성된 section0.xml 문자열을 반환한다.

    Args:
        blocks: ``ast_walker.walk()`` 의 출력. 문맥 의존 규칙이 모두
            적용된 상태여야 한다.
        style_map: ``config.load_style_map()`` 의 반환 딕셔너리.

    Returns:
        XML 선언 ``<?xml ...?>`` 로 시작하고 ``hs:sec`` 루트로 감싼
        완전한 XML 문자열. ``hp:secPr`` 블록은 부트스트랩에서 가져온다.
    """
    raise NotImplementedError("build_section 은 후속 커밋에서 구현된다")
