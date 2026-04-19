"""HWPX(ZIP) 패키저 (계약 2, C 영역).

C 부재 기간 동안 B 가 임시 구현. mimetype 을 ZIP 의 첫 엔트리로 무압축
저장하는 것이 핵심 책임이며, 이 규칙이 깨지면 한/글이 파일을 열지 못한다
(개발자 핸드오프 §시나리오 4 의 95% 원인).
"""

from __future__ import annotations

import zipfile
from pathlib import Path


__all__ = ["package_hwpx"]


def package_hwpx(work_dir: str | Path, output_path: str | Path) -> None:
    """work_dir 의 내용을 HWPX 로 패키징해 output_path 에 쓴다."""
    work_dir = Path(work_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mimetype_path = work_dir / "mimetype"
    if not mimetype_path.is_file():
        raise FileNotFoundError(f"mimetype 누락: {mimetype_path}")

    with zipfile.ZipFile(output_path, "w") as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, mimetype_path.read_bytes())

        for path in sorted(_iter_files(work_dir)):
            rel = path.relative_to(work_dir).as_posix()
            if rel == "mimetype":
                continue
            zf.write(path, arcname=rel, compress_type=zipfile.ZIP_DEFLATED)


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and ".DS_Store" not in path.name:
            yield path
