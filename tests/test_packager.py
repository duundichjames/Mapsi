"""mapsi.packager 단위 테스트."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mapsi.packager import package_hwpx


REQUIRED_FILES = (
    "mimetype",
    "version.xml",
    "settings.xml",
    "META-INF/container.xml",
    "META-INF/manifest.xml",
    "Contents/header.xml",
    "Contents/section0.xml",
    "Contents/content.hpf",
)


def _write_required_structure(work_dir: Path) -> None:
    for rel_path in REQUIRED_FILES:
        path = work_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)

        if rel_path == "mimetype":
            path.write_bytes(b"application/hwp+zip")
        elif rel_path.endswith(".xml") or rel_path.endswith(".hpf"):
            path.write_text("<root/>", encoding="utf-8")
        else:
            path.write_text("dummy", encoding="utf-8")


def test_package_hwpx_creates_valid_zip_with_required_entries(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "out" / "sample.hwpx"
    work_dir.mkdir()

    _write_required_structure(work_dir)

    package_hwpx(work_dir, output_path)

    assert output_path.is_file()
    assert zipfile.is_zipfile(output_path)

    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()

    for rel_path in REQUIRED_FILES:
        assert rel_path in names


def test_mimetype_is_first_entry_and_stored(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "sample.hwpx"
    work_dir.mkdir()

    _write_required_structure(work_dir)

    package_hwpx(work_dir, output_path)

    with zipfile.ZipFile(output_path) as zf:
        infos = zf.infolist()

    assert infos[0].filename == "mimetype"
    assert infos[0].compress_type == zipfile.ZIP_STORED
    assert infos[0].extra == b""


def test_non_mimetype_files_are_deflated(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "sample.hwpx"
    work_dir.mkdir()

    _write_required_structure(work_dir)

    package_hwpx(work_dir, output_path)

    with zipfile.ZipFile(output_path) as zf:
        info_map = {info.filename: info for info in zf.infolist()}

    assert info_map["Contents/header.xml"].compress_type == zipfile.ZIP_DEFLATED
    assert info_map["Contents/section0.xml"].compress_type == zipfile.ZIP_DEFLATED
    assert info_map["Contents/content.hpf"].compress_type == zipfile.ZIP_DEFLATED


def test_ignores_os_artifacts(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "sample.hwpx"
    work_dir.mkdir()

    _write_required_structure(work_dir)

    (work_dir / ".DS_Store").write_text("junk", encoding="utf-8")
    (work_dir / "Thumbs.db").write_text("junk", encoding="utf-8")

    macosx_dir = work_dir / "__MACOSX"
    macosx_dir.mkdir()
    (macosx_dir / "junk.txt").write_text("junk", encoding="utf-8")

    trashes_dir = work_dir / ".Trashes"
    trashes_dir.mkdir()
    (trashes_dir / "junk.txt").write_text("junk", encoding="utf-8")

    package_hwpx(work_dir, output_path)

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())

    assert ".DS_Store" not in names
    assert "Thumbs.db" not in names
    assert "__MACOSX/junk.txt" not in names
    assert ".Trashes/junk.txt" not in names


def test_raises_when_required_file_missing(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "sample.hwpx"
    work_dir.mkdir()

    _write_required_structure(work_dir)
    (work_dir / "Contents" / "section0.xml").unlink()

    with pytest.raises(FileNotFoundError, match="section0.xml"):
        package_hwpx(work_dir, output_path)


def test_raises_when_mimetype_signature_is_invalid(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "sample.hwpx"
    work_dir.mkdir()

    _write_required_structure(work_dir)
    (work_dir / "mimetype").write_bytes(b"application/zip")

    with pytest.raises(ValueError, match="mimetype"):
        package_hwpx(work_dir, output_path)


def test_work_dir_is_not_modified_or_deleted(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    output_path = tmp_path / "sample.hwpx"
    work_dir.mkdir()

    _write_required_structure(work_dir)
    original_files = sorted(
        str(path.relative_to(work_dir))
        for path in work_dir.rglob("*")
        if path.is_file()
    )

    package_hwpx(work_dir, output_path)

    assert work_dir.is_dir()

    current_files = sorted(
        str(path.relative_to(work_dir))
        for path in work_dir.rglob("*")
        if path.is_file()
    )
    assert current_files == original_files
