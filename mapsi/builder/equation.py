"""hp:equation 빌더.

LaTeX 수식 문자열을 받아 ``hp:equation`` XML 요소를 생성한다. LaTeX 의 HNC
변환은 ``mapsi.math.converter.convert_equation`` 에 위임하므로, 본 모듈은
변환 결과를 hp:script 슬롯에 끼워 넣는 조립 책임만 갖는다.
"""

from __future__ import annotations

from lxml import etree


__all__ = ["build_equation"]


def build_equation(latex: str, display: bool) -> etree._Element:
    """LaTeX 수식을 받아 hp:equation 노드를 생성한다.

    Args:
        latex: 마크다운 원문에서 추출한 LaTeX 본문 ($ 또는 $$ 제외).
        display: True 면 디스플레이 수식(독립 단락), False 면 인라인.

    Returns:
        ``hp:equation`` 루트 요소. 내부 ``hp:script`` 의 텍스트는
        ``mapsi.math.converter.convert_equation`` 의 반환값이다.
    """
    raise NotImplementedError("build_equation 은 후속 커밋에서 구현된다")
