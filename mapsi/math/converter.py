"""LaTeX → 한/글 HNC 수식 변환 (계약 7, C 영역)."""

from __future__ import annotations

import os
from textwrap import dedent

from .cache import cache_key, load, save


__all__ = ["convert_equation"]


_SYSTEM_PROMPT = dedent(
    """
    너는 LaTeX 수식을 한/글 HNC 수식 문법으로 변환하는 변환기다.
    설명 없이 변환 결과 문자열만 반환한다.

    예시:
    LaTeX: \\frac{a}{b}
    HNC: {a} over {b}

    LaTeX: \\sqrt{x}
    HNC: sqrt x

    LaTeX: \\alpha + \\beta
    HNC: alpha + beta

    LaTeX: \\sum_{i=1}^{n} a_i
    HNC: sum from {i=1} to n a_i

    LaTeX: \\int_0^1 x^2 dx
    HNC: int from 0 to 1 x^2 dx
    """
).strip()


def _fallback(latex: str) -> str:
    return f"[hnc 수식]{latex}[/hnc 수식]"


def convert_equation(latex: str, display: bool) -> str:
    """LaTeX 수식을 한/글 HNC 수식 문법으로 변환한다."""
    normalized_latex = latex.strip()
    fallback = _fallback(normalized_latex)

    if os.environ.get("MAPSI_NO_LLM"):
        return fallback

    key = cache_key(normalized_latex)
    cache = load()
    cached = cache.get(key)
    if isinstance(cached, str) and cached.strip():
        return cached

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not anthropic_key and not openai_key:
        return fallback

    try:
        if anthropic_key:
            result = _call_anthropic(normalized_latex, display)
        else:
            result = _call_openai(normalized_latex, display)
    except Exception:
        return fallback

    if not isinstance(result, str) or not result.strip():
        return fallback

    result = result.strip()
    cache[key] = result

    try:
        save(cache)
    except OSError:
        pass

    return result


def _user_prompt(latex: str, display: bool) -> str:
    mode = "display" if display else "inline"
    return dedent(
        f"""
        수식 유형: {mode}
        LaTeX: {latex}

        위 LaTeX 를 한/글 HNC 수식 문법으로 변환하라.
        설명 없이 결과 문자열만 출력하라.
        """
    ).strip()


def _call_anthropic(latex: str, display: bool) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=os.environ.get("MAPSI_ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
        max_tokens=256,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _user_prompt(latex, display),
            }
        ],
    )
    return "".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()


def _call_openai(latex: str, display: bool) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model=os.environ.get("MAPSI_OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(latex, display)},
        ],
    )

    message = response.choices[0].message.content
    return message.strip() if isinstance(message, str) else ""
