"""LaTeX → 한/글 HNC 수식 변환 (계약 7, C 영역).

C 부재 기간 동안 B 가 스텁으로 둔다. 폴백 동작(API 키 없음 또는 호출 실패) 만
구현되어 있어 LLM 미사용 환경에서도 일관된 출력을 보장한다.
"""

from __future__ import annotations

import os


__all__ = ["convert_equation"]


def _fallback(latex: str) -> str:
    return f"[hnc 수식]{latex}[/hnc 수식]"


def convert_equation(latex: str, display: bool) -> str:
    """LaTeX 수식을 한/글 HNC 수식 문법으로 변환한다.

    스텁 단계 동작:
        환경 변수 ``MAPSI_NO_LLM`` 이 설정되어 있거나 API 키가 없으면
        즉시 폴백 문자열을 반환한다. API 호출 자체는 후속 커밋에서 구현.
    """
    if os.environ.get("MAPSI_NO_LLM"):
        return _fallback(latex)
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        return _fallback(latex)
    return _fallback(latex)
