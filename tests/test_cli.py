"""``mapsi.cli`` 단위 테스트.

두 종류의 테스트가 합쳐져 있다:

A. ``_load_dotenv_if_available()`` 회귀 보호 (B 옵션)
   * 프로젝트 ``.env`` 가 셸 환경 변수보다 **우선**한다 (``override=True``).
   * ``.env`` 가 ``OPENAI_API_KEY`` 만 정의하고 ``OPENAI_API_BASE`` /
     ``OPENAI_BASE_URL`` 은 비워둔 경우, 셸에 미리 박혀 있던 base URL 변수가
     깨끗이 제거되어야 한다 (Gemini 호환 엔드포인트 등 비-OpenAI proxy 가
     진짜 OpenAI 키를 가로채는 사고 방지).
   * ``.env`` 가 base URL 도 명시하면 그 값이 그대로 살아 있어야 한다.
   * ``.env`` 자체가 없으면 셸 환경을 건드리지 않는다.

B. ``main()`` E2E (C 본 구현)
   * 정상 변환 시 exit code 0
   * 입력 파일 누락 시 3
   * style-map 누락 시 3
   * dry-run 시 출력 파일 안 만들고 role 분포 stdout 출력
   * ``--no-llm`` 사용 후 ``MAPSI_NO_LLM`` 환경 변수가 새지 않음
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("dotenv", reason="python-dotenv 가 없으면 .env 로딩이 비활성화된다")

from mapsi.cli import _load_dotenv_if_available, main  # noqa: E402


# --------------------------------------------------------------------------- #
# A. _load_dotenv_if_available — .env 우선 정책 회귀                            #
# --------------------------------------------------------------------------- #

@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``.env`` 검색을 ``tmp_path`` 로 격리한다."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _clear_openai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL"):
        monkeypatch.delenv(var, raising=False)


def test_dotenv_overrides_shell_openai_key(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """셸에 키가 박혀 있어도 ``.env`` 값이 이긴다."""
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "shell-injected-key")
    (isolated_cwd / ".env").write_text("OPENAI_API_KEY=dotenv-key\n", encoding="utf-8")

    _load_dotenv_if_available()

    assert os.environ["OPENAI_API_KEY"] == "dotenv-key"


def test_dotenv_strips_shell_base_url_when_only_key_defined(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """안전망: ``.env`` 가 키만 주고 base 를 안 주면 셸의 base 는 사라진다."""
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv(
        "OPENAI_API_BASE",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    (isolated_cwd / ".env").write_text(
        "OPENAI_API_KEY=sk-proj-real-openai\n", encoding="utf-8"
    )

    _load_dotenv_if_available()

    assert os.environ["OPENAI_API_KEY"] == "sk-proj-real-openai"
    assert "OPENAI_API_BASE" not in os.environ
    assert "OPENAI_BASE_URL" not in os.environ


def test_dotenv_keeps_explicit_base_url(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``.env`` 가 base URL 을 명시하면 그 값이 environment 에 살아 있다."""
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_BASE", "https://shell.invalid/v1")
    (isolated_cwd / ".env").write_text(
        "OPENAI_API_KEY=dotenv-key\nOPENAI_API_BASE=https://my-proxy.example/v1\n",
        encoding="utf-8",
    )

    _load_dotenv_if_available()

    assert os.environ["OPENAI_API_KEY"] == "dotenv-key"
    assert os.environ["OPENAI_API_BASE"] == "https://my-proxy.example/v1"


def test_safety_net_skipped_when_dotenv_has_no_openai_key(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``.env`` 에 OpenAI 키가 없으면 base URL 정리도 일어나지 않는다.

    이 사용자는 OpenAI 가 아닌 다른 프로바이더만 쓰는 상황이므로 셸의
    OpenAI 관련 변수는 그대로 둬야 한다 (다른 도구가 의존할 수 있다).
    """
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://shell.invalid/v1")
    (isolated_cwd / ".env").write_text("ANTHROPIC_API_KEY=sk-ant-xxx\n", encoding="utf-8")

    _load_dotenv_if_available()

    assert os.environ["OPENAI_API_KEY"] == "shell-key"
    assert os.environ["OPENAI_API_BASE"] == "https://shell.invalid/v1"


def test_no_dotenv_file_leaves_environment_intact(
    isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``.env`` 자체가 없으면 셸 환경은 손대지 않는다."""
    _clear_openai_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "shell-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://shell.invalid/v1")
    assert not (isolated_cwd / ".env").exists()

    _load_dotenv_if_available()

    assert os.environ["OPENAI_API_KEY"] == "shell-key"
    assert os.environ["OPENAI_API_BASE"] == "https://shell.invalid/v1"


# --------------------------------------------------------------------------- #
# B. main() E2E — 입력 검증, exit code, 환경 누수                                #
# --------------------------------------------------------------------------- #

def test_main_returns_zero_on_success(
    samples_dir: Path, spec_dir: Path, tmp_path: Path
) -> None:
    input_md = samples_dir / "base" / "base.md"
    output_hwpx = tmp_path / "out" / "base.hwpx"

    rc = main(
        [
            str(input_md),
            "-o",
            str(output_hwpx),
            "--style-map",
            str(spec_dir / "styles.yaml"),
        ]
    )

    assert rc == 0
    assert output_hwpx.is_file()


def test_main_returns_3_when_input_missing(spec_dir: Path, tmp_path: Path) -> None:
    input_md = tmp_path / "missing.md"
    output_hwpx = tmp_path / "out.hwpx"

    rc = main(
        [
            str(input_md),
            "-o",
            str(output_hwpx),
            "--style-map",
            str(spec_dir / "styles.yaml"),
        ]
    )

    assert rc == 3
    assert not output_hwpx.exists()


def test_main_returns_3_when_style_map_missing(
    samples_dir: Path, tmp_path: Path
) -> None:
    input_md = samples_dir / "base" / "base.md"
    output_hwpx = tmp_path / "out.hwpx"
    missing_style_map = tmp_path / "missing.yaml"

    rc = main(
        [
            str(input_md),
            "-o",
            str(output_hwpx),
            "--style-map",
            str(missing_style_map),
        ]
    )

    assert rc == 3
    assert not output_hwpx.exists()


def test_dry_run_returns_zero_and_does_not_create_output(
    samples_dir: Path,
    spec_dir: Path,
    tmp_path: Path,
    capsys,
) -> None:
    input_md = samples_dir / "base" / "base.md"
    output_hwpx = tmp_path / "dry-run.hwpx"

    rc = main(
        [
            str(input_md),
            "-o",
            str(output_hwpx),
            "--style-map",
            str(spec_dir / "styles.yaml"),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()

    assert rc == 0
    assert not output_hwpx.exists()
    assert "블록 수:" in captured.out


def test_no_llm_flag_does_not_leak_environment(
    samples_dir: Path,
    spec_dir: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_md = samples_dir / "base" / "base.md"
    output_hwpx = tmp_path / "dry-run.hwpx"

    monkeypatch.delenv("MAPSI_NO_LLM", raising=False)

    rc = main(
        [
            str(input_md),
            "-o",
            str(output_hwpx),
            "--style-map",
            str(spec_dir / "styles.yaml"),
            "--dry-run",
            "--no-llm",
        ]
    )

    assert rc == 0
    assert os.environ.get("MAPSI_NO_LLM") is None
