"""``mapsi.math`` (cache + converter) 의 단위 테스트.

세션 conftest 가 ``MAPSI_NO_LLM=1`` 과 ``MAPSI_EQUATION_CACHE`` 임시 경로를
강제 설정해 두므로, 별도 격리 없이 폴백 경로 테스트를 진행할 수 있다.
LLM 분기 테스트는 환경 변수와 SDK 호출을 ``monkeypatch`` 로 가짜로 채워
검증한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapsi.math import cache, converter


# ---------------------------------------------------------------------------
# cache.py
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """각 테스트 전용 캐시 파일을 환경 변수로 주입한다."""
    p = tmp_path / "equation_cache.json"
    monkeypatch.setenv("MAPSI_EQUATION_CACHE", str(p))
    return p


class TestCacheKey:
    def test_same_latex_same_display_same_key(self) -> None:
        assert cache.cache_key("a^2", False) == cache.cache_key("a^2", False)

    def test_display_changes_key(self) -> None:
        assert cache.cache_key("a^2", False) != cache.cache_key("a^2", True)

    def test_different_latex_different_key(self) -> None:
        assert cache.cache_key("a^2", False) != cache.cache_key("b^2", False)

    def test_key_is_16_hex_chars(self) -> None:
        k = cache.cache_key("\\frac{a}{b}", True)
        assert len(k) == 16
        assert all(c in "0123456789abcdef" for c in k)


class TestCachePath:
    def test_env_override_takes_precedence(
        self, isolated_cache: Path
    ) -> None:
        assert cache.cache_path() == isolated_cache

    def test_no_env_falls_back_to_home(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MAPSI_EQUATION_CACHE", raising=False)
        assert cache.cache_path() == Path.home() / ".mapsi" / "equation_cache.json"


class TestCacheLoadSave:
    def test_load_missing_file_returns_empty(
        self, isolated_cache: Path
    ) -> None:
        assert cache.load() == {}

    def test_save_then_load_roundtrip(self, isolated_cache: Path) -> None:
        cache.save({"abc": "{a} over {b}"})
        assert cache.load() == {"abc": "{a} over {b}"}

    def test_save_creates_parent_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "nested" / "dir" / "cache.json"
        monkeypatch.setenv("MAPSI_EQUATION_CACHE", str(target))
        cache.save({"k": "v"})
        assert target.is_file()

    def test_corrupt_file_falls_back_to_empty(
        self, isolated_cache: Path
    ) -> None:
        isolated_cache.write_text("not json{{{", encoding="utf-8")
        assert cache.load() == {}

    def test_non_dict_top_level_falls_back_to_empty(
        self, isolated_cache: Path
    ) -> None:
        isolated_cache.write_text("[1, 2, 3]", encoding="utf-8")
        assert cache.load() == {}


class TestCacheLookupStore:
    def test_lookup_miss(self, isolated_cache: Path) -> None:
        assert cache.lookup("\\sqrt{x}", False) is None

    def test_store_then_lookup(self, isolated_cache: Path) -> None:
        cache.store("\\sqrt{x}", False, "sqrt {x}")
        assert cache.lookup("\\sqrt{x}", False) == "sqrt {x}"

    def test_store_does_not_collide_across_display(
        self, isolated_cache: Path
    ) -> None:
        cache.store("a", False, "INLINE")
        cache.store("a", True, "DISPLAY")
        assert cache.lookup("a", False) == "INLINE"
        assert cache.lookup("a", True) == "DISPLAY"


# ---------------------------------------------------------------------------
# converter.py
# ---------------------------------------------------------------------------


class TestConvertEquationFallback:
    """API 키가 없거나 ``MAPSI_NO_LLM`` 일 때 LaTeX 원문이 마커에 박힌다."""

    def test_no_llm_env_returns_latex_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAPSI_NO_LLM", "1")
        out = converter.convert_equation("a^2 + b^2 = c^2", False)
        assert out == "[hnc 수식]a^2 + b^2 = c^2[/hnc 수식]"

    def test_no_keys_returns_latex_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        out = converter.convert_equation("\\frac{a}{b}", True)
        assert out == "[hnc 수식]\\frac{a}{b}[/hnc 수식]"

    def test_strips_whitespace_inside_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAPSI_NO_LLM", "1")
        # 양옆 \n / 공백은 strip 되어 마커 안에 들어간다.
        out = converter.convert_equation("\n  E = mc^2  \n", True)
        assert out == "[hnc 수식]E = mc^2[/hnc 수식]"

    def test_empty_latex_yields_empty_marker_body(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAPSI_NO_LLM", "1")
        assert converter.convert_equation("", False) == "[hnc 수식][/hnc 수식]"


class TestConvertEquationLLMBranching:
    """LLM 호출 분기가 우선순위와 폴백 규약을 정확히 따른다."""

    def test_anthropic_called_when_only_anthropic_key(
        self, monkeypatch: pytest.MonkeyPatch, isolated_cache: Path
    ) -> None:
        monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        called = {"anthropic": 0, "openai": 0}

        def fake_anthropic(latex: str, display: bool) -> str:
            called["anthropic"] += 1
            return "{a} over {b}"

        def fake_openai(latex: str, display: bool) -> str:
            called["openai"] += 1
            return "OPENAI"

        monkeypatch.setattr(converter, "_call_anthropic", fake_anthropic)
        monkeypatch.setattr(converter, "_call_openai", fake_openai)

        out = converter.convert_equation("\\frac{a}{b}", False)
        assert out == "[hnc 수식]{a} over {b}[/hnc 수식]"
        assert called == {"anthropic": 1, "openai": 0}

    def test_openai_called_when_only_openai_key(
        self, monkeypatch: pytest.MonkeyPatch, isolated_cache: Path
    ) -> None:
        monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "y")
        called: list[str] = []

        monkeypatch.setattr(
            converter,
            "_call_openai",
            lambda latex, display: (called.append("o"), "OPENAI_RESULT")[1],
        )
        out = converter.convert_equation("x", False)
        assert out == "[hnc 수식]OPENAI_RESULT[/hnc 수식]"
        assert called == ["o"]

    def test_anthropic_priority_over_openai(
        self, monkeypatch: pytest.MonkeyPatch, isolated_cache: Path
    ) -> None:
        monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        monkeypatch.setenv("OPENAI_API_KEY", "y")
        called: list[str] = []
        monkeypatch.setattr(
            converter,
            "_call_anthropic",
            lambda latex, display: (called.append("a"), "ANT")[1],
        )
        monkeypatch.setattr(
            converter,
            "_call_openai",
            lambda latex, display: (called.append("o"), "OPN")[1],
        )
        out = converter.convert_equation("x", False)
        assert "ANT" in out and called == ["a"]

    def test_anthropic_failure_falls_through_to_openai(
        self, monkeypatch: pytest.MonkeyPatch, isolated_cache: Path
    ) -> None:
        monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        monkeypatch.setenv("OPENAI_API_KEY", "y")

        def boom(latex: str, display: bool) -> str:
            raise RuntimeError("network error")

        monkeypatch.setattr(converter, "_call_anthropic", boom)
        monkeypatch.setattr(
            converter, "_call_openai", lambda latex, display: "OPN"
        )
        out = converter.convert_equation("x", False)
        assert out == "[hnc 수식]OPN[/hnc 수식]"

    def test_all_failures_fall_through_to_latex_marker(
        self, monkeypatch: pytest.MonkeyPatch, isolated_cache: Path
    ) -> None:
        monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        monkeypatch.setenv("OPENAI_API_KEY", "y")

        def boom(latex: str, display: bool) -> str:
            raise RuntimeError("oops")

        monkeypatch.setattr(converter, "_call_anthropic", boom)
        monkeypatch.setattr(converter, "_call_openai", boom)
        out = converter.convert_equation("\\sqrt{2}", False)
        assert out == "[hnc 수식]\\sqrt{2}[/hnc 수식]"


class TestConvertEquationCaching:
    """LLM 결과는 캐시에 저장되고 다음 호출에서 hit 한다."""

    def test_result_is_cached_after_llm_call(
        self, monkeypatch: pytest.MonkeyPatch, isolated_cache: Path
    ) -> None:
        monkeypatch.delenv("MAPSI_NO_LLM", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        calls = {"n": 0}

        def fake(latex: str, display: bool) -> str:
            calls["n"] += 1
            return "FROM_LLM"

        monkeypatch.setattr(converter, "_call_anthropic", fake)
        out1 = converter.convert_equation("a", False)
        out2 = converter.convert_equation("a", False)
        assert out1 == out2 == "[hnc 수식]FROM_LLM[/hnc 수식]"
        # LLM 은 처음 1 번만 호출.
        assert calls["n"] == 1
        # 디스크에도 저장됐는지.
        stored = json.loads(isolated_cache.read_text(encoding="utf-8"))
        assert "FROM_LLM" in stored.values()

    def test_no_llm_does_not_pollute_cache(
        self, monkeypatch: pytest.MonkeyPatch, isolated_cache: Path
    ) -> None:
        monkeypatch.setenv("MAPSI_NO_LLM", "1")
        converter.convert_equation("a", False)
        assert not isolated_cache.exists()


class TestCleanResponse:
    def test_strip_whitespace(self) -> None:
        assert converter._clean_response("  hello\n") == "hello"

    def test_unwrap_code_fence(self) -> None:
        raw = "```hnc\n{a} over {b}\n```"
        assert converter._clean_response(raw) == "{a} over {b}"

    def test_unwrap_code_fence_no_lang(self) -> None:
        raw = "```\nE=mc^2\n```"
        assert converter._clean_response(raw) == "E=mc^2"

    def test_no_fence_passthrough(self) -> None:
        assert converter._clean_response("plain") == "plain"
