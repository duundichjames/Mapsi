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

    체크포인트 1 단계의 한시적 동작:
        파서/빌더 미구현 동안, 평문 단락만 포함하는 마크다운에 대해서는
        base 부트스트랩의 section0.xml 을 그대로 통과시켜 한/글이 파일을
        열 수 있는지부터 검증한다. 헤딩/목록 등이 등장하면 즉시
        NotImplementedError 로 빠진다 (실제 빌더 구현 시점에 폐기).
    """
    from .packager import package_hwpx

    md_path = Path(md_path)
    output_path = Path(output_path)
    work_dir = Path(work_dir)

    _bootstrap_workdir(work_dir)
    if _is_plain_text_only(md_path):
        # 부트스트랩이 이미 base 의 section0.xml 을 work_dir 에 복사해둔 상태.
        # 별도 작업 없이 그대로 패키징한다.
        package_hwpx(str(work_dir), str(output_path))
        return

    from .builder.section import build_section
    from .parser import parse_markdown
    from .ast_walker import walk

    blocks = parse_markdown(md_path)
    walked = walk(blocks)
    section_xml = build_section(walked, style_map)
    (work_dir / "Contents" / "section0.xml").write_text(section_xml, encoding="utf-8")

    package_hwpx(str(work_dir), str(output_path))


def _is_plain_text_only(md_path: Path) -> bool:
    """평문 단락(YAML front matter + 빈 줄 + 평문) 만으로 구성됐는지 판정.

    헤딩(``#``), 목록(``-``/``*``/숫자), 인용(``>``), 코드펜스(``\u0060\u0060\u0060``),
    표(``|``), 이미지(``![``), 수식(``$``) 같은 마크다운 메타문자가 한 번이라도
    줄 시작에 등장하면 평문이 아니다.
    """
    text = md_path.read_text(encoding="utf-8")

    # YAML front matter 제거
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            text = text[end + 4 :]

    META_PREFIXES = ("#", "-", "*", "+", ">", "```", "~~~", "|", "![", "$$")
    for raw in text.splitlines():
        line = raw.lstrip()
        if not line:
            continue
        if line.startswith(META_PREFIXES):
            return False
        if line[:2].rstrip().isdigit() and line.lstrip("0123456789").startswith("."):
            return False
    return True


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
    # section0.xml 은 빌더가 덮어쓰는 게 정상 경로. 스모크 단계 동안에는
    # base 의 section0.xml 을 placeholder 로 두어 그대로 통과 가능하게 한다.
    shutil.copy2(bootstrap / "Contents" / "section0.xml",
                 work_dir / "Contents" / "section0.xml")
