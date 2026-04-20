"""HWPX(ZIP) 패키저 (계약 2, C 영역).

mimetype 을 ZIP 의 첫 엔트리로 무압축(STORED) 저장하는 것이 핵심 책임이며,
그 외 파일은 DEFLATE 로 압축한다. work_dir 자체는 변형하지 않는다.
"""

from __future__ import annotations

import zipfile
from pathlib import Path


__all__ = ["package_hwpx"]


_REQUIRED_FILES = (
    "mimetype",
    "version.xml",
    "settings.xml",
    "META-INF/container.xml",
    "META-INF/manifest.xml",
    "Contents/header.xml",
    "Contents/section0.xml",
    "Contents/content.hpf",
)

_IGNORED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}

_IGNORED_DIR_PREFIXES = (
    "__MACOSX/",
    ".AppleDouble/",
    ".Spotlight-V100/",
    ".Trashes/",
    ".fseventsd/",
)

_MIMETYPE_SIGNATURE = b"application/hwp+zip"


def package_hwpx(work_dir: str | Path, output_path: str | Path) -> None:
    """work_dir 의 내용을 HWPX(ZIP) 로 패키징해 output_path 에 쓴다."""
    work_dir = Path(work_dir)
    output_path = Path(output_path)

    if not work_dir.is_dir():
        raise FileNotFoundError(f"work_dir 가 존재하지 않음: {work_dir}")

    _validate_required_files(work_dir)

    mimetype_path = work_dir / "mimetype"
    mimetype_bytes = mimetype_path.read_bytes()
    if mimetype_bytes != _MIMETYPE_SIGNATURE:
        raise ValueError(
            "mimetype 내용이 올바르지 않음: "
            f"{mimetype_bytes!r} (expected={_MIMETYPE_SIGNATURE!r})"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w") as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        info.extra = b""
        zf.writestr(info, mimetype_bytes)

        for path in _iter_files(work_dir):
            rel_path = path.relative_to(work_dir).as_posix()
            if rel_path == "mimetype":
                continue
            zf.write(path, arcname=rel_path, compress_type=zipfile.ZIP_DEFLATED)


def _validate_required_files(work_dir: Path) -> None:
    missing = [rel for rel in _REQUIRED_FILES if not (work_dir / rel).is_file()]
    if missing:
        joined = ", ".join(missing)
        raise FileNotFoundError(
            f"work_dir 에 필수 파일이 누락됨: {joined} (work_dir={work_dir})"
        )


def _iter_files(root: Path):
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue

        rel_path = path.relative_to(root).as_posix()
        if _should_ignore(rel_path):
            continue

        files.append(path)

    yield from sorted(files, key=lambda p: p.relative_to(root).as_posix())


def _should_ignore(rel_path: str) -> bool:
    name = Path(rel_path).name
    if name in _IGNORED_FILE_NAMES:
        return True
    return any(rel_path.startswith(prefix) for prefix in _IGNORED_DIR_PREFIXES)
