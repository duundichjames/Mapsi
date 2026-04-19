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

    1. 부트스트랩  -- 정적 템플릿 + base 자산을 work_dir 로 복사
    2. 파싱       -- ``parse_markdown`` 으로 평탄 Block 리스트 생성
    3. AST 워크    -- ``walk`` 가 문맥 의존 규칙을 적용
    4. 빌드       -- ``build_section`` 이 section0.xml 바이트 생성
    5. 패키징      -- ``package_hwpx`` 가 work_dir 을 .hwpx ZIP 으로 묶음
    """
    from .ast_walker import walk
    from .builder.header import parse_style_table
    from .builder.section import build_section
    from .packager import package_hwpx
    from .parser import parse_markdown

    md_path = Path(md_path)
    output_path = Path(output_path)
    work_dir = Path(work_dir)

    repo_root = Path(__file__).resolve().parents[1]
    base_section = (
        repo_root / "samples" / "base" / "unpacked" / "Contents" / "section0.xml"
    )

    _bootstrap_workdir(work_dir)

    blocks = parse_markdown(md_path)
    walked = walk(blocks)

    header_bytes = (work_dir / "Contents" / "header.xml").read_bytes()
    style_table = parse_style_table(header_bytes)
    section_xml = build_section(walked, style_map, style_table, base_section)
    (work_dir / "Contents" / "section0.xml").write_bytes(section_xml)

    package_hwpx(str(work_dir), str(output_path))


def _bootstrap_workdir(work_dir: Path) -> None:
    """work_dir 에 정적 템플릿과 부트스트랩 자산을 복사한다.

    부트스트랩 출처는 ``samples/base/unpacked`` (settings.xml 과
    content.hpf 의 제공원). 정적 템플릿은 ``templates/`` (mimetype,
    version.xml, META-INF, Contents/header.xml).

    section0.xml 은 빌더가 덮어쓸 예정이므로 여기서는 복사하지 않는다.
    """
    repo_root = Path(__file__).resolve().parents[1]
    templates = repo_root / "templates"
    bootstrap = repo_root / "samples" / "base" / "unpacked"

    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "Contents").mkdir(exist_ok=True)
    (work_dir / "META-INF").mkdir(exist_ok=True)

    for rel in (
        "mimetype",
        "version.xml",
        "META-INF/container.xml",
        "META-INF/container.rdf",
        "META-INF/manifest.xml",
    ):
        shutil.copy2(templates / rel, work_dir / rel)
    shutil.copy2(
        templates / "Contents" / "header.xml",
        work_dir / "Contents" / "header.xml",
    )

    shutil.copy2(bootstrap / "settings.xml", work_dir / "settings.xml")
    shutil.copy2(
        bootstrap / "Contents" / "content.hpf",
        work_dir / "Contents" / "content.hpf",
    )
