"""mapsi.math.converter 단위 테스트."""

from __future__ import annotations

import pytest

from mapsi.math import converter
from mapsi.math.cache import cache_key


@pytest.fixture
def isolated_cache(monkeypatch):
    store: dict[str, str] = {}

    monkeypatch.setattr(converter, "load", lambda: store.copy())

    def fake_save(cache: dict[str, str]) -> None:
        store.clear()
        store.update(cache)

    monkeypatch.setattr(converter, "save", fake_save)
    return store


def test_convert_equation_returns_fallback_when_no_llm_flag_set(
    monkeypatch,
    isolated_cache,
) -> None:
    monkeypatch.setenv("MAPSI_NO_LLM", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = converter.convert_equation(r"\frac{a}{b}", display=False)

    assert result == r"[hnc 수식]\frac{a}{b}[/hnc 수식]"


def test_convert_equation_returns_fallback_when_no_api_keys(
    monkeypatch,
    isolated_cache,
) -> None:
    monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = converter.convert_equation(r"\alpha + \beta", display=False)

    assert result == r"[hnc 수식]\alpha + \beta[/hnc 수식]"


def test_convert_equation_uses_cached_result_before_calling_provider(
    monkeypatch,
    isolated_cache,
) -> None:
    latex = r"\sqrt{x}"
    isolated_cache[cache_key(latex)] = "cached-hnc"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key")

    def fail_call(*args, **kwargs):
        raise AssertionError("provider should not be called when cache is hit")

    monkeypatch.setattr(converter, "_call_anthropic", fail_call)
    monkeypatch.setattr(converter, "_call_openai", fail_call)

    result = converter.convert_equation(latex, display=False)

    assert result == "cached-hnc"


def test_convert_equation_prefers_anthropic_when_both_keys_exist(
    monkeypatch,
    isolated_cache,
) -> None:
    latex = r"\int_0^1 x^2 dx"
    calls: list[tuple[str, str, bool]] = []

    monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    def fake_anthropic(input_latex: str, display: bool) -> str:
        calls.append(("anthropic", input_latex, display))
        return "anthropic-result"

    def fail_openai(*args, **kwargs):
        raise AssertionError("OpenAI should not be called when Anthropic key exists")

    monkeypatch.setattr(converter, "_call_anthropic", fake_anthropic)
    monkeypatch.setattr(converter, "_call_openai", fail_openai)

    result = converter.convert_equation(latex, display=True)

    assert result == "anthropic-result"
    assert calls == [("anthropic", latex, True)]
    assert isolated_cache[cache_key(latex)] == "anthropic-result"


def test_convert_equation_uses_openai_when_only_openai_key_exists(
    monkeypatch,
    isolated_cache,
) -> None:
    latex = r"\sum_{i=1}^{n} a_i"
    calls: list[tuple[str, str, bool]] = []

    monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    def fake_openai(input_latex: str, display: bool) -> str:
        calls.append(("openai", input_latex, display))
        return "openai-result"

    monkeypatch.setattr(converter, "_call_openai", fake_openai)

    result = converter.convert_equation(latex, display=False)

    assert result == "openai-result"
    assert calls == [("openai", latex, False)]
    assert isolated_cache[cache_key(latex)] == "openai-result"


def test_convert_equation_falls_back_when_provider_raises(
    monkeypatch,
    isolated_cache,
) -> None:
    latex = r"\frac{x}{y}"

    monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def failing_provider(*args, **kwargs):
        raise RuntimeError("provider failure")

    monkeypatch.setattr(converter, "_call_anthropic", failing_provider)

    result = converter.convert_equation(latex, display=False)

    assert result == r"[hnc 수식]\frac{x}{y}[/hnc 수식]"
    assert cache_key(latex) not in isolated_cache


def test_convert_equation_falls_back_when_provider_returns_blank(
    monkeypatch,
    isolated_cache,
) -> None:
    latex = r"\beta"

    monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    monkeypatch.setattr(converter, "_call_openai", lambda *_args, **_kwargs: "   ")

    result = converter.convert_equation(latex, display=False)

    assert result == r"[hnc 수식]\beta[/hnc 수식]"
    assert cache_key(latex) not in isolated_cache
