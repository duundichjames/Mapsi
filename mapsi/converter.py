"""변환 파이프라인 오케스트레이터.

본 파일은 50 줄 이내로 유지한다 (계획서 "B 담당 범위" 의 제약). 실제 작업은
``parser`` / ``ast_walker`` / ``builder`` / ``packager`` 모듈에 위임하며,
본 함수의 책임은 호출 순서와 산출물의 work_dir 배치뿐이다.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


__all__ = ["md_to_hwpx"]


def md_to_hwpx(
    md_path: str | Path,
    output_path: str | Path,
    style_map: dict[str, Any],
    work_dir: str | Path,
) -> None:
    """마크다운 파일을 HWPX 로 변환한다 (계약 6).

    파이프라인 5 단계는 ``spec/interfaces.md`` 에 정의된 순서를 따른다.
    """
    from .builder.section import build_section
    from .packager import package_hwpx
    from .parser import parse_markdown
    from .ast_walker import walk

    md_path = Path(md_path)
    output_path = Path(output_path)
    work_dir = Path(work_dir)

    blocks = parse_markdown(md_path)
    walked = walk(blocks)
    section_xml = build_section(walked, style_map)

    _bootstrap_workdir(work_dir)
    (work_dir / "Contents" / "section0.xml").write_text(section_xml, encoding="utf-8")

    package_hwpx(str(work_dir), str(output_path))


def _bootstrap_workdir(work_dir: Path) -> None:
    """work_dir 에 정적 템플릿과 부트스트랩 자산을 복사한다.

    현 단계의 부트스트랩 출처는 ``samples/base/unpacked`` (settings.xml
    과 content.hpf 의 제공원). 정적 템플릿은 ``templates/`` (mimetype,
    version.xml, META-INF, Contents/header.xml).
    """
    repo_root = Path(__file__).resolve().parents[1]
    templates = repo_root / "templates"
    bootstrap = repo_root / "samples" / "base" / "unpacked"

    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "Contents").mkdir(exist_ok=True)
    (work_dir / "META-INF").mkdir(exist_ok=True)

    for rel in ("mimetype", "version.xml", "META-INF/container.xml",
                "META-INF/container.rdf", "META-INF/manifest.xml"):
        shutil.copy2(templates / rel, work_dir / rel)
    shutil.copy2(templates / "Contents" / "header.xml",
                 work_dir / "Contents" / "header.xml")

    shutil.copy2(bootstrap / "settings.xml", work_dir / "settings.xml")
    shutil.copy2(bootstrap / "Contents" / "content.hpf",
                 work_dir / "Contents" / "content.hpf")
