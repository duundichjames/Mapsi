"""``mapsi.inspect`` 의 단위 테스트.

라이브러리 API (extract_paragraph_sequence, filter_nonempty,
extract_style_id_to_name) 와 CLI (main) 양쪽 모두 검증.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mapsi.config import load_style_map
from mapsi.converter import md_to_hwpx
from mapsi.inspect import (
    ParagraphInfo,
    extract_paragraph_sequence,
    extract_style_id_to_name,
    filter_nonempty,
    main,
)


@pytest.fixture(scope="module")
def headings_hwpx(repo_root: Path, tmp_path_factory) -> Path:
    """``tests/golden/01_headings`` 를 변환한 결과 .hwpx 를 모듈 단위 캐시."""
    tmp = tmp_path_factory.mktemp("inspect_headings")
    out = tmp / "01_headings.hwpx"
    work = tmp / "work"
    work.mkdir()
    md = repo_root / "tests" / "golden" / "01_headings" / "input.md"
    style_map = load_style_map(repo_root / "spec" / "styles.yaml")
    md_to_hwpx(md_path=md, output_path=out, style_map=style_map, work_dir=work)
    return out


# ---------------------------------------------------------------------------
# 라이브러리 API
# ---------------------------------------------------------------------------


class TestExtractParagraphSequence:
    def test_returns_paragraph_info_list(self, headings_hwpx: Path) -> None:
        seq = extract_paragraph_sequence(headings_hwpx)
        assert len(seq) > 0
        for info in seq:
            assert isinstance(info, ParagraphInfo)
            assert isinstance(info.style_name, str)
            assert isinstance(info.style_id, str)
            assert isinstance(info.text, str)

    def test_style_id_and_name_are_consistent(self, headings_hwpx: Path) -> None:
        """(id=4, 개요 1), (id=3, 본문) 같은 알려진 매핑이 들어 있다."""
        seq = extract_paragraph_sequence(headings_hwpx)
        pairs = {(info.style_id, info.style_name) for info in seq}
        assert ("3", "본문") in pairs
        assert ("4", "개요 1") in pairs


class TestExtractStyleIdToName:
    def test_known_styles_present(self, templates_dir: Path) -> None:
        header = (templates_dir / "Contents" / "header.xml").read_bytes()
        mapping = extract_style_id_to_name(header)
        assert mapping["0"] == "바탕글"
        assert mapping["3"] == "본문"
        assert mapping["4"] == "개요 1"
        assert mapping["8"] == "인용"
        assert mapping["9"] == "코드"


class TestFilterNonempty:
    def test_drops_empty_text(self) -> None:
        seq = [
            ParagraphInfo("바탕글", "0", ""),
            ParagraphInfo("본문", "3", "안녕"),
            ParagraphInfo("본문", "3", ""),
        ]
        assert filter_nonempty(seq) == [ParagraphInfo("본문", "3", "안녕")]

    def test_empty_input_yields_empty_output(self) -> None:
        assert filter_nonempty([]) == []


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------


class TestCli:
    def test_basic_output_contains_style_names_and_texts(
        self, headings_hwpx: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main([str(headings_hwpx)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "본문 단락입니다." in out
        assert "제목1" in out
        assert "본문" in out
        assert "개요 1" in out
        assert str(headings_hwpx) in out  # 파일명 헤더

    def test_styles_mode_prints_definition_summary(
        self, headings_hwpx: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main([str(headings_hwpx), "--styles"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "[사용된 스타일 정의]" in out
        assert "[정합성]" in out
        assert "OK" in out  # 정합성 통과 표시

    def test_all_mode_includes_empty_paragraphs(
        self, headings_hwpx: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--all`` 은 빈 단락(secPr 호스트 등) 도 출력한다."""
        rc_default = main([str(headings_hwpx)])
        out_default = capsys.readouterr().out
        rc_all = main([str(headings_hwpx), "--all"])
        out_all = capsys.readouterr().out
        assert rc_default == 0 and rc_all == 0
        # --all 의 출력 줄 수가 기본보다 많거나 같다 (빈 단락 만큼 더)
        lines_default = [ln for ln in out_default.splitlines() if ln.strip().startswith(tuple("0123456789"))]
        lines_all = [ln for ln in out_all.splitlines() if ln.strip().startswith(tuple("0123456789"))]
        assert len(lines_all) >= len(lines_default)

    def test_missing_file_returns_nonzero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ghost = tmp_path / "does_not_exist.hwpx"
        rc = main([str(ghost)])
        assert rc != 0
        err = capsys.readouterr().err
        assert "없다" in err or "오류" in err

    def test_multiple_files_each_get_a_header(
        self, headings_hwpx: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        copy = tmp_path / "copy.hwpx"
        shutil.copy2(headings_hwpx, copy)
        rc = main([str(headings_hwpx), str(copy)])
        assert rc == 0
        out = capsys.readouterr().out
        assert out.count("===") >= 4  # 두 파일 × 양쪽 ===


# ---------------------------------------------------------------------------
# Phase 7 — 각주 (footnote) 표시
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def footnote_hwpx(repo_root: Path, tmp_path_factory) -> Path:
    """``tests/golden/07_footnote`` 를 변환한 .hwpx 캐시."""
    tmp = tmp_path_factory.mktemp("inspect_footnote")
    out = tmp / "07_footnote.hwpx"
    work = tmp / "work"
    work.mkdir()
    md = repo_root / "tests" / "golden" / "07_footnote" / "input.md"
    style_map = load_style_map(repo_root / "spec" / "styles.yaml")
    md_to_hwpx(md_path=md, output_path=out, style_map=style_map, work_dir=work)
    return out


def test_footnote_body_text_excludes_footnote_node_text(
    footnote_hwpx: Path,
) -> None:
    """본문 단락의 텍스트는 hp:footNote 안의 텍스트를 *포함하지 않는다*.

    포함되면 본문 마커 위치마다 각주 본문이 중복 표시되어 검증 시 노이즈가
    된다 (Phase 7 inspect 정리의 핵심 회귀 가드).
    """
    seq = filter_nonempty(extract_paragraph_sequence(footnote_hwpx))
    body_paragraphs = [info for info in seq if info.style_name == "본문"]
    assert body_paragraphs, "본문 단락이 1 개 이상 있어야 한다"
    for info in body_paragraphs:
        # 각주 본문 텍스트의 식별 토큰이 새지 않아야 함
        assert "각주 본문" not in info.text, (
            f"본문 단락 텍스트에 각주 본문이 새고 있음: {info.text!r}"
        )


def test_footnote_paragraphs_appear_separately_with_각주_style(
    footnote_hwpx: Path,
) -> None:
    """각주 본문은 별도 hp:p (styleIDRef=각주) 로 따로 열거된다."""
    seq = filter_nonempty(extract_paragraph_sequence(footnote_hwpx))
    fn_paragraphs = [info for info in seq if info.style_name == "각주"]
    assert len(fn_paragraphs) == 2
    # 한/글 표기 관습대로 본문 앞에 공백 1개가 붙는다.
    assert fn_paragraphs[0].text.startswith(" ")
    assert "첫번째" in fn_paragraphs[0].text
    assert "두번째" in fn_paragraphs[1].text
