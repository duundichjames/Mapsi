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
    *,
    allow_missing_images: bool = False,
    missing_images_report: list[str] | None = None,
) -> None:
    """마크다운 파일을 HWPX 로 변환한다 (계약 6).

    파이프라인 5 단계는 ``spec/interfaces.md`` 에 정의된 순서를 따른다.

    1. 부트스트랩  -- 정적 템플릿 + base 자산을 work_dir 로 복사
    2. 파싱       -- ``parse_markdown`` 으로 평탄 Block 리스트 생성
    3. AST 워크    -- ``walk`` 가 문맥 의존 규칙을 적용
    4. 빌드       -- ``build_section`` 이 section0.xml 바이트 생성
    5. 패키징      -- ``package_hwpx`` 가 work_dir 을 .hwpx ZIP 으로 묶음

    Parameters
    ----------
    allow_missing_images:
        ``True`` 면 Markdown 이 참조한 이미지 파일이 존재하지 않을 때
        ``FileNotFoundError`` 를 던지는 대신 번들 placeholder PNG
        (``mapsi/assets/image_not_found.png``) 로 대체한다. figure Block 의
        alt 텍스트/캡션은 "이미지 로드 실패" 표식을 포함하도록 재작성된다.
        기본값 ``False`` — CLI 와 기존 골든의 엄격한 동작을 유지하기 위함.
    missing_images_report:
        제공되면 누락된 원본 ``src`` 문자열이 이 리스트에 append 된다.
        UI 가 사용자에게 경고 배너를 띄울 때 사용한다 (동일 src 는 한 번만).
    """
    from .ast_walker import walk
    from .builder.header import parse_style_table
    from .builder.manifest import update_manifest
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

    image_map, manifest_entries = _register_figure_images(
        walked,
        md_path.parent,
        work_dir,
        allow_missing_images=allow_missing_images,
        missing_report=missing_images_report,
    )
    if manifest_entries:
        update_manifest(
            work_dir / "Contents" / "content.hpf", manifest_entries
        )

    header_bytes = (work_dir / "Contents" / "header.xml").read_bytes()
    style_table = parse_style_table(header_bytes)
    section_xml = build_section(
        walked, style_map, style_table, base_section, image_map=image_map
    )
    (work_dir / "Contents" / "section0.xml").write_bytes(section_xml)

    package_hwpx(str(work_dir), str(output_path))


# pixel → HWPUNIT 환산 (한/글 표준: 1 inch = 7200 HWPUNIT). PNG 의 DPI
# 정보가 없으면 96 dpi 가정.
_DEFAULT_DPI = 96.0
_HWPUNIT_PER_INCH = 7200.0

# 원본 이미지를 찾지 못했을 때 (allow_missing_images=True) 대신 삽입할 번들
# placeholder. 패키지에 동봉되어 pip install 환경에서도 접근 가능하다
# (``pyproject.toml`` 의 ``tool.setuptools.package-data`` 참조).
_MISSING_IMAGE_PLACEHOLDER = (
    Path(__file__).resolve().parent / "assets" / "image_not_found.png"
)


def _register_figure_images(
    blocks: list,
    md_dir: Path,
    work_dir: Path,
    *,
    allow_missing_images: bool = False,
    missing_report: list[str] | None = None,
) -> tuple[dict[str, dict], list[dict]]:
    """walked Block 리스트에서 ``role="figure"`` 들의 이미지를 등록한다.

    같은 ``src`` 가 여러 figure 에서 참조되면 한 번만 BinData 에 복사하고
    동일 ``binary_item_id`` 를 공유한다.

    ``allow_missing_images=True`` 이고 ``src`` 파일이 존재하지 않으면
    번들 placeholder PNG 로 대체하고, 해당 Block 의 ``text`` / ``meta``
    를 재작성해 한/글 문서에서 "이미지 로드 실패" 가 명시적으로 보이도록
    한다. 누락된 모든 figure Block 이 대상이다 (동일 src 재사용 포함).

    Returns
    -------
    (image_map, manifest_entries)
        - ``image_map``: ``src`` 문자열 → ``{"binary_item_id",
          "width_hwpunit", "height_hwpunit"}``. ``build_section`` 이
          ``build_figure_paragraph`` 에 넘긴다.
        - ``manifest_entries``: ``update_manifest`` 에 그대로 전달.

    Raises
    ------
    FileNotFoundError
        ``allow_missing_images=False`` 인데 figure 의 ``src`` 가 ``md_dir``
        기준으로 존재하지 않을 때.
    """
    from PIL import Image

    from .builder.bindata import register_image

    image_map: dict[str, dict] = {}
    entries: list[dict] = []
    placeholder_info: dict | None = None

    def _ensure_placeholder() -> dict:
        """placeholder 를 단 한 번 BinData 에 등록하고 info dict 를 반환."""
        nonlocal placeholder_info
        if placeholder_info is not None:
            return placeholder_info
        if not _MISSING_IMAGE_PLACEHOLDER.is_file():
            raise FileNotFoundError(
                f"번들 placeholder 이미지 누락: {_MISSING_IMAGE_PLACEHOLDER}"
            )
        with Image.open(_MISSING_IMAGE_PLACEHOLDER) as img:
            width_px, height_px = img.size
            dpi_x, dpi_y = img.info.get("dpi", (_DEFAULT_DPI, _DEFAULT_DPI))
        item_id, entry = register_image(_MISSING_IMAGE_PLACEHOLDER, work_dir)
        placeholder_info = {
            "binary_item_id": item_id,
            "width_hwpunit": int(round(width_px * _HWPUNIT_PER_INCH / dpi_x)),
            "height_hwpunit": int(
                round(height_px * _HWPUNIT_PER_INCH / dpi_y)
            ),
        }
        entries.append(entry)
        return placeholder_info

    for blk in blocks:
        if getattr(blk, "role", None) != "figure":
            continue
        src = blk.meta.get("src") if blk.meta else None
        if not src:
            continue
        resolved = (md_dir / src).resolve()
        if not resolved.is_file():
            if not allow_missing_images:
                raise FileNotFoundError(
                    f"figure 원본을 찾을 수 없음: {resolved} "
                    f"(md='{md_dir}', src='{src}')"
                )
            _rewrite_missing_figure_block(blk, src)
            if missing_report is not None and src not in missing_report:
                missing_report.append(src)
            if src not in image_map:
                image_map[src] = _ensure_placeholder()
            continue
        if src in image_map:
            continue
        with Image.open(resolved) as img:
            width_px, height_px = img.size
            dpi_x, dpi_y = img.info.get("dpi", (_DEFAULT_DPI, _DEFAULT_DPI))
        item_id, entry = register_image(resolved, work_dir)
        image_map[src] = {
            "binary_item_id": item_id,
            "width_hwpunit": int(round(width_px * _HWPUNIT_PER_INCH / dpi_x)),
            "height_hwpunit": int(
                round(height_px * _HWPUNIT_PER_INCH / dpi_y)
            ),
        }
        entries.append(entry)
    return image_map, entries


def _rewrite_missing_figure_block(blk: Any, src: str) -> None:
    """누락된 figure Block 의 alt / caption 을 "이미지 로드 실패" 표식으로 갱신.

    placeholder PNG 자체는 항상 동일하지만, 사용자가 원본 Markdown 의 어느
    이미지가 실패했는지 문서 안에서 식별할 수 있어야 하므로 **원본 src** 와
    기존 alt / caption 을 메시지에 포함시킨다. Block 인스턴스는 mutable
    dataclass 이므로 in-place 로 갱신해도 builder 가 그대로 읽는다.
    """
    original_alt = (blk.text or "").strip()
    if original_alt:
        blk.text = f"[이미지 로드 실패] {original_alt}"
    else:
        blk.text = "[이미지 로드 실패]"

    meta = blk.meta if isinstance(blk.meta, dict) else {}
    original_caption = (meta.get("caption") or "").strip()
    if original_caption:
        meta["caption"] = f"이미지 로드 실패: {src} — {original_caption}"
    else:
        meta["caption"] = f"이미지 로드 실패: {src}"
    blk.meta = meta


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
