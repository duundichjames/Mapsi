"""mapsi.cli 단위 테스트."""

from __future__ import annotations

import os
from pathlib import Path

from mapsi.cli import main


def test_main_returns_zero_on_success(samples_dir: Path, spec_dir: Path, tmp_path: Path) -> None:
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


def test_main_returns_3_when_style_map_missing(samples_dir: Path, tmp_path: Path) -> None:
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
