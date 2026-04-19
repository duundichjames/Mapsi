"""LaTeX → 한/글 HNC 수식 변환 (계약 7, C 영역).

ADR 0002 결정에 따라 ``mapsi`` 의 수식 출력은 평문 마커 모드를 사용한다:

    [hnc 수식]<변환 결과>[/hnc 수식]

본 모듈의 책임은 ``<변환 결과>`` 부분을 결정하는 것이다. 우선순위:

1. ``MAPSI_NO_LLM`` 환경 변수가 설정되어 있으면 즉시 폴백 (= LaTeX 원문).
   테스트 / CI / 오프라인 환경의 결정론을 보장한다.
2. ``ANTHROPIC_API_KEY`` 가 있으면 Anthropic Messages API 호출.
3. 없고 ``OPENAI_API_KEY`` 가 있으면 OpenAI Chat Completions API 호출.
4. 호출이 예외를 던지거나 빈 응답을 반환하면 폴백 (조용히, 변환은 끝까지
   굴러가야 함).
5. 성공 시 결과를 ``mapsi.math.cache`` 에 저장 (다음 호출에서 hit).

LLM 에 보내는 프롬프트는 :data:`_SYSTEM_PROMPT` 와 :func:`_user_prompt` 에
정의되어 있으며, "한/글 HNC 수식 문법으로만 답하라" 를 강하게 요구한다.
응답이 코드 블록 (```` ```hnc ... ``` ````) 으로 감싸져 있으면 자동
unwrap 한다.

캐시 키는 ``(latex, display)`` 쌍이며, 마커는 캐시에 *포함하지 않는다*
(저수준 변환 결과만 저장).
"""

from __future__ import annotations

import logging
import os
import re

from . import cache


__all__ = ["convert_equation"]


_LOG = logging.getLogger(__name__)

_MARKER_OPEN = "[hnc 수식]"
_MARKER_CLOSE = "[/hnc 수식]"


def convert_equation(latex: str, display: bool) -> str:
    """LaTeX 수식 1 개를 한/글 HNC 마커 텍스트로 변환한다.

    Parameters
    ----------
    latex:
        마크다운에서 추출한 LaTeX 원문 (``$ ... $`` 또는 ``$$ ... $$`` 의
        delimiter 는 제거된 본문). 좌우 공백은 호출자가 정리해서 전달한다.
    display:
        ``True`` 이면 디스플레이 모드 (``$$ ... $$``), ``False`` 이면 인라인
        모드 (``$ ... $``). LLM 프롬프트와 캐시 키에 모두 영향.

    Returns
    -------
    str
        ``"[hnc 수식]<변환 결과>[/hnc 수식]"`` 형태의 평문. 빌더는 이
        문자열을 그대로 ``hp:t`` 에 박는다.
    """
    stripped = latex.strip()

    if os.environ.get("MAPSI_NO_LLM"):
        return _wrap(stripped)

    cached = cache.lookup(stripped, display)
    if cached is not None:
        return _wrap(cached)

    converted = _try_llm(stripped, display)
    if converted is None:
        return _wrap(stripped)

    try:
        cache.store(stripped, display, converted)
    except OSError as exc:
        _LOG.warning("수식 캐시 저장 실패 (무시): %s", exc)
    return _wrap(converted)


def _wrap(body: str) -> str:
    return f"{_MARKER_OPEN}{body}{_MARKER_CLOSE}"


def _try_llm(latex: str, display: bool) -> str | None:
    """LLM 호출 시도. 실패/키 없음 시 ``None`` 반환."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _call_anthropic(latex, display)
        except Exception as exc:
            _LOG.warning("Anthropic 호출 실패 → 폴백: %s", exc)
    if os.environ.get("OPENAI_API_KEY"):
        try:
            return _call_openai(latex, display)
        except Exception as exc:
            _LOG.warning("OpenAI 호출 실패 → 폴백: %s", exc)
    return None


_SYSTEM_PROMPT = (
    "너는 LaTeX 수식을 한/글 HNC 수식 문법으로 변환하는 전문가이다. "
    "응답에는 변환된 HNC 수식 문자열만 포함하고, 설명·주석·코드 블록·"
    "마커 (`[hnc 수식]` 등) 는 절대 포함하지 마라. "
    "예시: `\\frac{a}{b}` → `{a} over {b}`, `\\sqrt{x}` → `sqrt {x}`, "
    "`x^2` → `x^2`, `\\sum_{i=1}^{n}` → `sum _{i=1} ^{n}`."
)


def _user_prompt(latex: str, display: bool) -> str:
    mode = "디스플레이 (별도 줄)" if display else "인라인 (본문 흐름)"
    return f"모드: {mode}\nLaTeX:\n{latex}"


def _call_anthropic(latex: str, display: bool) -> str:
    """Anthropic Messages API. ``anthropic`` SDK 미설치 시 ImportError."""
    from anthropic import Anthropic  # type: ignore

    client = Anthropic()
    msg = client.messages.create(
        model=os.environ.get("MAPSI_ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _user_prompt(latex, display)}],
    )
    parts = [
        getattr(b, "text", "")
        for b in msg.content
        if getattr(b, "type", None) == "text"
    ]
    return _clean_response("".join(parts))


def _call_openai(latex: str, display: bool) -> str:
    """OpenAI Chat Completions API. ``openai`` SDK 미설치 시 ImportError."""
    from openai import OpenAI  # type: ignore

    client = OpenAI()
    resp = client.chat.completions.create(
        model=os.environ.get("MAPSI_OPENAI_MODEL", "gpt-4o-mini"),
        max_tokens=512,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(latex, display)},
        ],
    )
    return _clean_response(resp.choices[0].message.content or "")


_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n(.*?)\n```$", re.DOTALL)


def _clean_response(raw: str) -> str:
    """LLM 응답을 정리: 좌우 공백 + 코드 블록 unwrap."""
    text = raw.strip()
    m = _CODE_FENCE_RE.match(text)
    if m is not None:
        text = m.group(1).strip()
    return text
