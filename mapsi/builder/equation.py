"""hp:equation 빌더.

LaTeX 수식 문자열을 받아 ``hp:equation`` XML 요소를 생성한다. LaTeX 의 HNC
변환은 :mod:`mapsi.math.latex_parser` + :mod:`mapsi.math.hnc` 에 위임하며,
변환 실패(미지원 명령어/파싱 실패) 시에는 LaTeX 원문을 그대로 ``hp:script``
에 보존한다(폴백). 고정 속성·자식 구조는 한/글이 직접 만든 hp:equation
표본(spec/equation_samples/한글수식표본.hwpx) 분석으로 확정한 값이다.
"""

from __future__ import annotations

import random

from lxml import etree

from ..math import hnc


__all__ = ["build_equation"]


# 네임스페이스 — 다른 빌더(section.py, elements.py) 와 동일 방식.
HWPML_PARA_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HP = f"{{{HWPML_PARA_NS}}}"
# xml:space 용 예약 네임스페이스 (lxml 이 'xml' 접두사로 직렬화).
_XML_NS = "http://www.w3.org/XML/1998/namespace"


# hp:equation 고정 속성 (한/글 실측 표본 기준). id·zOrder 만 가변.
_EQUATION_FIXED_ATTRS: dict[str, str] = {
    "numberingType": "EQUATION",
    "textWrap": "TOP_AND_BOTTOM",
    "textFlow": "BOTH_SIDES",
    "lock": "0",
    "dropcapstyle": "None",
    "version": "Equation Version 60",
    "textColor": "#000000",
    "baseUnit": "1000",
    "lineMode": "CHAR",
    "font": "HancomEQN",
    "baseLine": "72",
}

# hp:sz — 한/글이 수식을 열 때 재계산하므로 표본의 흔한 기본값을 둔다.
_SZ_ATTRS: dict[str, str] = {
    "width": "4627",
    "height": "1163",
    "widthRelTo": "ABSOLUTE",
    "heightRelTo": "ABSOLUTE",
    "protect": "0",
}

# hp:pos — 글자처럼 취급(treatAsChar) 되는 인라인 객체 기본 배치.
_POS_ATTRS: dict[str, str] = {
    "treatAsChar": "1",
    "affectLSpacing": "0",
    "flowWithText": "1",
    "allowOverlap": "0",
    "holdAnchorAndSO": "0",
    "vertRelTo": "PARA",
    "horzRelTo": "PARA",
    "vertAlign": "TOP",
    "horzAlign": "LEFT",
    "vertOffset": "0",
    "horzOffset": "0",
}

# hp:outMargin — 좌우 56, 상하 0.
_OUT_MARGIN_ATTRS: dict[str, str] = {
    "left": "56",
    "right": "56",
    "top": "0",
    "bottom": "0",
}


# id 채번: hp:equation 은 hp:tbl·hp:pic·각주 instId 와 같은 객체 id 공간을
# 공유하므로, 저장소의 기존 관례(elements.py) 와 동일하게 [1, 2**31-1] 난수를
# 쓴다. 충돌 확률을 다른 객체와 균일하게 맞추고 일관성을 유지한다.
def _next_equation_id() -> str:
    return str(random.randint(1, 2**31 - 1))


def build_equation(latex: str, display: bool) -> etree._Element:
    """LaTeX 수식을 받아 hp:equation 노드를 생성한다.

    Args:
        latex: 마크다운 원문에서 추출한 LaTeX 본문 ($ 또는 $$ 제외).
        display: 인라인/디스플레이 구분. **본 빌더에서는 사용하지 않는다** —
            표본 분석상 그 차이는 hp:equation 속성이 아니라 단락 배치로
            드러나므로, 향후 ``elements.py`` 의 단락 조립 단계에서 처리한다.
            시그니처는 유지한다.

    Returns:
        ``hp:equation`` 루트 요소. 내부 ``hp:script`` 텍스트는 변환 성공 시
        HNC 문자열, 실패 시 LaTeX 원문(폴백).
    """
    del display  # 시그니처 유지용; 인라인/디스플레이 구분은 단락 조립에서.

    result = hnc.to_hnc(latex)
    script_text = result.hnc if result.ok else latex

    eq = etree.Element(f"{_HP}equation")
    eq.set("id", _next_equation_id())
    eq.set("zOrder", "0")  # 우선 0; 호출부에서 순서 관리 가능.
    for key, value in _EQUATION_FIXED_ATTRS.items():
        eq.set(key, value)

    sz = etree.SubElement(eq, f"{_HP}sz")
    for key, value in _SZ_ATTRS.items():
        sz.set(key, value)

    pos = etree.SubElement(eq, f"{_HP}pos")
    for key, value in _POS_ATTRS.items():
        pos.set(key, value)

    out_margin = etree.SubElement(eq, f"{_HP}outMargin")
    for key, value in _OUT_MARGIN_ATTRS.items():
        out_margin.set(key, value)

    script = etree.SubElement(eq, f"{_HP}script")
    script.set(f"{{{_XML_NS}}}space", "preserve")
    script.text = script_text

    return eq
