"""인라인 서식 마크 조합 → ``charPrIDRef`` 룩업 (Phase 10).

ADR 0004 의 결정 3·4 를 구현한다. 마크다운 인라인 서식 (``**bold``,
``*italic*``, ``~~strike~~``, ``` `code` ```) 의 활성 집합 (``frozenset``)
을 키로, ``templates/Contents/header.xml`` 에 사전 등록된 charPr ID
문자열을 돌려준다.

설계 노트
----------
``hh:charPr`` 는 정적 사전이며 한 ``hp:run`` 의 ``charPrIDRef`` 는 정수
1 개다. 즉 *동적 조립* (예: bold 한 charPr 와 italic 한 charPr 의
"오버레이") 은 HWPML 모델에 존재하지 않는다. 대신 자주 쓰는 조합만
미리 등록하고 (5 종, ID 25~29), 빌더가 마크 집합을 키로 매핑한다.

링크 (``link``) 는 다른 인라인 마크와 달리 *고정* ``charPr`` (= "하이퍼링크",
ID :data:`HYPERLINK_CHARPR_ID`, 파란 글자 + 밑줄) 로 처리하고, 런 자체를
``hp:fieldBegin/fieldEnd`` 쌍으로 감싼다. 즉 "조합 룩업 테이블" 대상이
아니므로 본 테이블에 등재하지 않는다. bold/italic 과 같은 다른 마크와
겹쳐도 링크 세그먼트는 하이퍼링크 charPr 로만 렌더링한다 (일관성 ·
클릭 가능성이 시각 서식보다 우선. ADR 0004 결정 1 v0.1.1 업데이트).

디그레이드 정책
----------------
조합 키가 사전에 없으면 마크 1 개씩 우선순위로 fallback 한다.

우선순위: ``bold`` > ``italic`` > ``strike`` > ``code``

예: ``{bold, italic, strike}`` → 사전에 없음 → ``strike`` 를 떨어뜨려
``{bold, italic}`` (=27) 으로 매핑. 시각 손실은 strike 1 개, 평문은
사라지지 않는다. 빈 집합은 본문 charPr ID (= ``"7"``) 를 돌려준다.
"""

from __future__ import annotations

from typing import Iterable


__all__ = [
    "BODY_CHARPR_ID",
    "HYPERLINK_CHARPR_ID",
    "INLINE_MARK_KINDS",
    "INLINE_CHARPR",
    "MARK_PRIORITY",
    "resolve_charpr",
]


BODY_CHARPR_ID = "7"
"""본문 charPr ID. 인라인 마크가 비어 있을 때 사용된다."""


HYPERLINK_CHARPR_ID = "30"
"""하이퍼링크 charPr ID (파란 글자 + 밑줄).

``templates/Contents/header.xml`` 의 ``hh:charProperties/hh:charPr[@id='30']``
에 정의된다 (textColor ``#0563C1``, underline SOLID ``#0563C1``). Builder 는
``kind="link"`` 인 inline mark 세그먼트의 모든 run 에 이 ID 를 부여한다."""

INLINE_MARK_KINDS = frozenset({"bold", "italic", "strike", "code"})
"""v0.1 에서 시각 서식을 부여하는 인라인 마크 종류.

``link`` 는 라벨만 보존하고 서식을 부여하지 않으므로 본 집합에 포함하지
않는다.
"""

INLINE_CHARPR: dict[frozenset[str], str] = {
    frozenset({"bold"}):                 "25",
    frozenset({"italic"}):               "26",
    frozenset({"bold", "italic"}):       "27",
    frozenset({"strike"}):               "28",
    frozenset({"code"}):                 "29",
}
"""사전 등록된 마크 조합 → charPr ID 매핑.

키는 ``frozenset`` 이라 마크 등장 순서에 무관 (``{bold, italic}`` 와
``{italic, bold}`` 가 같은 키). 값은 ``header.xml`` 의 ``hh:charPr/@id``
문자열.
"""

MARK_PRIORITY: tuple[str, ...] = ("bold", "italic", "strike", "code")
"""디그레이드 시 살릴 마크 우선순위 (앞이 높음).

조합이 ``INLINE_CHARPR`` 에 없을 때, 우선순위가 낮은 마크부터 떨어뜨려
사전에 있는 가장 가까운 조합을 만든다.
"""


def resolve_charpr(marks: Iterable[str]) -> str:
    """마크 집합으로부터 charPr ID 를 결정한다.

    Args:
        marks: 활성 인라인 마크 종류 (``"bold"`` / ``"italic"`` /
            ``"strike"`` / ``"code"``). 알 수 없는 종류는 조용히 무시.

    Returns:
        ``templates/Contents/header.xml`` 의 ``hh:charPr/@id`` 문자열.
        빈 입력은 본문 charPr (= :data:`BODY_CHARPR_ID`) 를 돌려준다.

    Notes:
        디그레이드 알고리즘:

        1. 알 수 없는 마크는 제거 (``INLINE_MARK_KINDS`` 와 교집합).
        2. 정확 매치가 있으면 즉시 반환.
        3. ``MARK_PRIORITY`` 의 *역순* (낮은 순위부터) 으로 마크를
           1 개씩 빼며 사전을 다시 본다.
        4. 마크 0 개로 줄면 본문 charPr 반환.
    """
    active = frozenset(m for m in marks if m in INLINE_MARK_KINDS)
    if not active:
        return BODY_CHARPR_ID
    if active in INLINE_CHARPR:
        return INLINE_CHARPR[active]
    remaining = set(active)
    for kind in reversed(MARK_PRIORITY):
        if kind in remaining:
            remaining.discard(kind)
            key = frozenset(remaining)
            if not key:
                return BODY_CHARPR_ID
            if key in INLINE_CHARPR:
                return INLINE_CHARPR[key]
    return BODY_CHARPR_ID
