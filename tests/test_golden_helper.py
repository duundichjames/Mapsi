"""``tests/_golden.py`` 헬퍼의 단위 테스트.

골든 회귀 테스트 자체가 통과하기 전에, 헬퍼가 기대대로 동작하는지
선검증. 입력은 ``samples/`` 의 정답 .hwpx 를 그대로 사용 (= 헬퍼는
정답 .hwpx 에 대해 알려진 결과를 내야 함).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._golden import (
    extract_paragraph_sequence,
    filter_nonempty,
    load_expected,
)


@pytest.fixture(scope="module")
def golden_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "golden"


@pytest.fixture(scope="module")
def headings_sample_hwpx(samples_dir: Path) -> Path:
    return samples_dir / "incremental" / "01_headings" / "01_headings.hwpx"


def test_extract_returns_paragraph_infos(headings_sample_hwpx: Path) -> None:
    """추출 결과는 1 개 이상의 ParagraphInfo 리스트."""
    seq = extract_paragraph_sequence(headings_sample_hwpx)
    assert len(seq) > 0
    for info in seq:
        assert isinstance(info.style_name, str)
        assert isinstance(info.text, str)


def test_style_ids_are_normalized_to_names(headings_sample_hwpx: Path) -> None:
    """raw ID 가 아니라 사람이 읽는 이름이 들어와야 한다.

    01_headings 정답에는 styleIDRef=2 가 "개요 1" 이지만, 09_equations
    기준 우리 템플릿에서는 styleIDRef=4 가 "개요 1" 이다. 헬퍼는
    각 .hwpx 자신의 header.xml 로 룩업하므로 이름은 항상 "개요 1" 이
    되어야 한다.
    """
    seq = extract_paragraph_sequence(headings_sample_hwpx)
    style_names = {info.style_name for info in seq}
    assert "개요 1" in style_names
    assert "개요 2" in style_names
    assert "개요 3" in style_names
    assert "개요 4" in style_names
    assert "개요 5" in style_names
    for name in style_names:
        assert not name.startswith("<unknown:"), f"미정의 스타일 ID: {name}"


def test_known_heading_paragraphs_in_01_headings(
    headings_sample_hwpx: Path,
) -> None:
    """01_headings 정답의 알려진 헤딩 위치(15~20)가 기대 시퀀스와 일치."""
    seq = extract_paragraph_sequence(headings_sample_hwpx)
    expected_slice = [
        ("개요 1", "제목1"),
        ("개요 2", "제목2"),
        ("개요 3", "제목3"),
        ("개요 4", "제목4"),
        ("개요 5", "제목5"),
        ("개요 5", ""),
    ]
    actual_slice = [(info.style_name, info.text) for info in seq[15:21]]
    assert actual_slice == expected_slice


def test_filter_nonempty_drops_empty_text(headings_sample_hwpx: Path) -> None:
    seq = extract_paragraph_sequence(headings_sample_hwpx)
    filtered = filter_nonempty(seq)
    assert len(filtered) <= len(seq)
    assert all(info.text != "" for info in filtered)


def test_load_expected_returns_dict_with_required_keys(golden_dir: Path) -> None:
    data = load_expected(golden_dir / "01_headings")
    assert "style_sequence" in data
    assert "text_sequence" in data
    assert isinstance(data["style_sequence"], list)
    assert isinstance(data["text_sequence"], list)
    assert len(data["style_sequence"]) == len(data["text_sequence"])


def test_expected_yaml_01_headings_content(golden_dir: Path) -> None:
    """우리가 손으로 작성한 expected 가 의도한 시퀀스를 갖는다."""
    data = load_expected(golden_dir / "01_headings")
    assert data["style_sequence"] == [
        "본문",
        "개요 1",
        "개요 1",
        "개요 2",
        "개요 3",
        "개요 4",
        "개요 5",
        "본문",
    ]
    assert data["text_sequence"] == [
        "본문 단락입니다.",
        "제목1",
        "제목1",
        "제목2",
        "제목3",
        "제목4",
        "제목5",
        "본문으로 복귀한 단락입니다.",
    ]
