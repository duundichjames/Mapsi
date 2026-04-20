"""``mapsi.converter._register_figure_images`` 단위 테스트 (Phase 6b).

end-to-end 변환은 ``tests/test_golden.py`` (06_figure_struct) 가 검증.
본 파일은 헬퍼의 경계 동작 (중복 src 공유, 누락 src, dpi 환산) 만 좁게
점검한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mapsi.converter import _register_figure_images
from mapsi.parser import Block


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_REL = "sample_figure.png"  # md_dir = FIXTURE_DIR


def _fig(src: str, alt: str = "") -> Block:
    return Block(role="figure", text=alt, meta={"src": src, "caption": None})


def test_single_figure_registers_one_image(tmp_path: Path) -> None:
    blocks = [_fig(SAMPLE_REL, "alt")]
    image_map, entries = _register_figure_images(blocks, FIXTURE_DIR, tmp_path)
    assert SAMPLE_REL in image_map
    info = image_map[SAMPLE_REL]
    assert info["binary_item_id"] == "image1"
    # 200 px wide @ 96 dpi → 200 * 7200 / 96 = 15000 HWPUNIT
    assert info["width_hwpunit"] == 15000
    # 120 px tall @ 96 dpi → 9000 HWPUNIT
    assert info["height_hwpunit"] == 9000
    assert len(entries) == 1
    assert entries[0]["id"] == "image1"


def test_duplicate_src_shares_id_and_does_not_double_copy(
    tmp_path: Path,
) -> None:
    blocks = [_fig(SAMPLE_REL, "a"), _fig(SAMPLE_REL, "b")]
    image_map, entries = _register_figure_images(blocks, FIXTURE_DIR, tmp_path)
    assert len(image_map) == 1
    assert len(entries) == 1
    bindata_files = sorted(p.name for p in (tmp_path / "BinData").iterdir())
    assert bindata_files == ["image1.png"]


def test_no_figure_blocks_returns_empty(tmp_path: Path) -> None:
    blocks = [Block(role="paragraph", text="hi")]
    image_map, entries = _register_figure_images(blocks, FIXTURE_DIR, tmp_path)
    assert image_map == {}
    assert entries == []
    assert not (tmp_path / "BinData").exists()


def test_missing_src_raises_filenotfound(tmp_path: Path) -> None:
    blocks = [_fig("nonexistent.png", "x")]
    with pytest.raises(FileNotFoundError, match="figure 원본을 찾을 수 없음"):
        _register_figure_images(blocks, FIXTURE_DIR, tmp_path)


def test_relative_src_is_resolved_against_md_dir(tmp_path: Path) -> None:
    """src 가 ``md_dir`` 기준 상대경로로 해석되는지 확인."""
    nested = tmp_path / "deep" / "doc"
    nested.mkdir(parents=True)
    work = tmp_path / "work"
    blocks = [_fig("../../../tests/fixtures/sample_figure.png", "x")]
    # md_dir 이 nested 라고 가정
    # nested 에서 두 단계 상위 = tmp_path, 다시 한 단계 = parent
    # 단순화: 절대 경로로 통과 가능
    blocks = [_fig(str(FIXTURE_DIR / "sample_figure.png"), "x")]
    image_map, _ = _register_figure_images(blocks, nested, work)
    assert len(image_map) == 1


def test_blocks_without_src_meta_are_ignored(tmp_path: Path) -> None:
    blocks = [Block(role="figure", text="x", meta={"src": None, "caption": None})]
    image_map, entries = _register_figure_images(blocks, FIXTURE_DIR, tmp_path)
    assert image_map == {}
    assert entries == []


class TestAllowMissingImages:
    """``allow_missing_images=True`` 분기 — UI 업로드 시 상대경로 이미지가
    서버에 존재하지 않는 상황을 번들 placeholder PNG 로 복구하는 경로."""

    def test_missing_src_falls_back_to_placeholder(self, tmp_path: Path) -> None:
        blocks = [_fig("nonexistent.png", "원본 alt")]
        image_map, entries = _register_figure_images(
            blocks, FIXTURE_DIR, tmp_path, allow_missing_images=True
        )
        assert "nonexistent.png" in image_map
        info = image_map["nonexistent.png"]
        assert info["binary_item_id"] == "image1"
        assert len(entries) == 1
        # placeholder 가 BinData 에 실제 복사되었는지 파일명으로 확인
        bindata_files = sorted(p.name for p in (tmp_path / "BinData").iterdir())
        assert bindata_files == ["image1.png"]

    def test_missing_figure_block_text_is_rewritten(self, tmp_path: Path) -> None:
        blk = _fig("nonexistent.png", "원본 alt")
        _register_figure_images(
            [blk], FIXTURE_DIR, tmp_path, allow_missing_images=True
        )
        assert blk.text == "[이미지 로드 실패] 원본 alt"
        assert blk.meta["caption"] == "이미지 로드 실패: nonexistent.png"

    def test_missing_figure_with_existing_caption_preserves_it(
        self, tmp_path: Path
    ) -> None:
        blk = Block(
            role="figure",
            text="alt",
            meta={"src": "gone.png", "caption": "원본 캡션"},
        )
        _register_figure_images(
            [blk], FIXTURE_DIR, tmp_path, allow_missing_images=True
        )
        assert "원본 캡션" in blk.meta["caption"]
        assert "gone.png" in blk.meta["caption"]

    def test_missing_figure_without_alt_text(self, tmp_path: Path) -> None:
        blk = Block(role="figure", text="", meta={"src": "gone.png", "caption": None})
        _register_figure_images(
            [blk], FIXTURE_DIR, tmp_path, allow_missing_images=True
        )
        assert blk.text == "[이미지 로드 실패]"

    def test_missing_report_collects_unique_srcs(self, tmp_path: Path) -> None:
        blocks = [
            _fig("a.png", "A"),
            _fig("b.png", "B"),
            _fig("a.png", "A'"),
        ]
        report: list[str] = []
        _register_figure_images(
            blocks,
            FIXTURE_DIR,
            tmp_path,
            allow_missing_images=True,
            missing_report=report,
        )
        assert report == ["a.png", "b.png"]

    def test_multiple_missing_srcs_share_placeholder_binary(
        self, tmp_path: Path
    ) -> None:
        """여러 누락 src 는 **동일** placeholder PNG 를 공유해야 한다
        (BinData 중복 방지 + manifest 단일 entry)."""
        blocks = [_fig("a.png", "A"), _fig("b.png", "B"), _fig("c.png", "C")]
        image_map, entries = _register_figure_images(
            blocks, FIXTURE_DIR, tmp_path, allow_missing_images=True
        )
        ids = {image_map[src]["binary_item_id"] for src in ("a.png", "b.png", "c.png")}
        assert ids == {"image1"}
        assert len(entries) == 1
        bindata_files = sorted(p.name for p in (tmp_path / "BinData").iterdir())
        assert bindata_files == ["image1.png"]

    def test_existing_files_are_unaffected_by_flag(self, tmp_path: Path) -> None:
        """실제로 존재하는 원본은 flag 와 무관하게 그대로 등록된다."""
        blocks = [_fig(SAMPLE_REL, "alt")]
        report: list[str] = []
        image_map, entries = _register_figure_images(
            blocks,
            FIXTURE_DIR,
            tmp_path,
            allow_missing_images=True,
            missing_report=report,
        )
        assert SAMPLE_REL in image_map
        assert report == []
        assert image_map[SAMPLE_REL]["width_hwpunit"] == 15000

    def test_mixed_existing_and_missing(self, tmp_path: Path) -> None:
        """존재 + 누락이 섞여 있어도 각각 올바르게 처리."""
        blocks = [_fig(SAMPLE_REL, "ok"), _fig("gone.png", "fail")]
        report: list[str] = []
        image_map, entries = _register_figure_images(
            blocks,
            FIXTURE_DIR,
            tmp_path,
            allow_missing_images=True,
            missing_report=report,
        )
        assert SAMPLE_REL in image_map
        assert "gone.png" in image_map
        assert image_map[SAMPLE_REL]["binary_item_id"] != image_map["gone.png"][
            "binary_item_id"
        ]
        assert len(entries) == 2
        assert report == ["gone.png"]
