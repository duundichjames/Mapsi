"""골든 회귀: 01_headings.

``tests/golden/01_headings/input.md`` 를 변환한 결과의 본문 단락
시퀀스가 ``expected.yaml`` 과 일치하는지 검증.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.config import load_style_map
from mapsi.converter import md_to_hwpx
from tests._golden import (
    extract_paragraph_sequence,
    filter_nonempty,
    load_expected,
)


@pytest.fixture(scope="module")
def fixture_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "golden" / "01_headings"


@pytest.fixture(scope="module")
def style_map(spec_dir: Path) -> dict:
    return load_style_map(spec_dir / "styles.yaml")


@pytest.fixture
def converted_hwpx(fixture_dir: Path, style_map: dict, tmp_path: Path) -> Path:
    out_path = tmp_path / "01_headings.hwpx"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    md_to_hwpx(
        md_path=fixture_dir / "input.md",
        output_path=out_path,
        style_map=style_map,
        work_dir=work_dir,
    )
    return out_path


def test_style_sequence_matches_expected(
    converted_hwpx: Path, fixture_dir: Path
) -> None:
    """변환 결과의 (스타일이름, 텍스트) 시퀀스가 expected.yaml 과 동일."""
    expected = load_expected(fixture_dir)
    seq = filter_nonempty(extract_paragraph_sequence(converted_hwpx))

    actual_styles = [info.style_name for info in seq]
    actual_texts = [info.text for info in seq]

    assert actual_styles == expected["style_sequence"]
    assert actual_texts == expected["text_sequence"]
