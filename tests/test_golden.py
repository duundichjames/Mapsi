"""골든 회귀 테스트 (자동 발견 + 파라미터화).

``tests/golden/<name>/`` 아래에 ``input.md`` 와 ``expected.yaml`` 이 모두
있는 디렉토리를 픽스처로 자동 인식하여, 각각에 대해 1 개의 테스트를 만든다.

새 픽스처를 추가하려면 디렉토리 + 두 파일만 만들면 된다. 본 파일은 수정
불필요. pytest 출력에서는 ``test_golden_fixture[01_headings]`` /
``test_golden_fixture[02_bullet_list]`` 식으로 분리되어 보인다.
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


_GOLDEN_ROOT = Path(__file__).parent / "golden"


def _discover_fixtures() -> list[str]:
    """``tests/golden/<name>/`` 중 input.md + expected.yaml 이 모두 있는 이름들."""
    if not _GOLDEN_ROOT.is_dir():
        return []
    names: list[str] = []
    for d in sorted(_GOLDEN_ROOT.iterdir()):
        if not d.is_dir():
            continue
        if (d / "input.md").exists() and (d / "expected.yaml").exists():
            names.append(d.name)
    return names


@pytest.mark.parametrize("fixture_name", _discover_fixtures())
def test_golden_fixture(
    fixture_name: str,
    repo_root: Path,
    spec_dir: Path,
    tmp_path: Path,
) -> None:
    """변환 결과의 (스타일 이름, 텍스트) 시퀀스가 expected.yaml 과 동일."""
    fixture_dir = _GOLDEN_ROOT / fixture_name
    out_path = tmp_path / f"{fixture_name}.hwpx"
    work_dir = tmp_path / "work"
    work_dir.mkdir()

    style_map = load_style_map(spec_dir / "styles.yaml")
    md_to_hwpx(
        md_path=fixture_dir / "input.md",
        output_path=out_path,
        style_map=style_map,
        work_dir=work_dir,
    )

    expected = load_expected(fixture_dir)
    seq = filter_nonempty(extract_paragraph_sequence(out_path))
    actual_styles = [info.style_name for info in seq]
    actual_texts = [info.text for info in seq]

    assert actual_styles == expected["style_sequence"], (
        f"[{fixture_name}] 스타일 시퀀스 불일치"
    )
    assert actual_texts == expected["text_sequence"], (
        f"[{fixture_name}] 텍스트 시퀀스 불일치"
    )
