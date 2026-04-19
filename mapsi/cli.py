"""CLI 엔트리포인트 (계약 5, C 영역)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import __version__


__all__ = ["main", "build_parser"]


_DEFAULT_STYLE_MAP = Path(__file__).resolve().parents[1] / "spec" / "styles.yaml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mapsi",
        description="마크다운을 한/글 HWPX 로 변환하는 Mapsi 변환기",
    )
    parser.add_argument("input", help="입력 마크다운 파일 경로")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="출력 HWPX 파일 경로",
    )
    parser.add_argument(
        "--style-map",
        default=str(_DEFAULT_STYLE_MAP),
        help=f"스타일 매핑 YAML 경로 (기본: {_DEFAULT_STYLE_MAP})",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="수식 변환에서 LLM 호출을 비활성화 (폴백만 사용)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="출력 파일을 쓰지 않고 파싱/워크 단계까지만 점검",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="상세 로그 출력",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mapsi {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    from .config import load_style_map
    from .converter import md_to_hwpx

    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    _configure_logging(args.verbose)
    log = logging.getLogger("mapsi.cli")

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_file():
        log.error("입력 파일을 찾을 수 없음: %s", input_path)
        return 3

    previous_no_llm = os.environ.get("MAPSI_NO_LLM")
    try:
        if args.no_llm:
            os.environ["MAPSI_NO_LLM"] = "1"
        else:
            os.environ.pop("MAPSI_NO_LLM", None)

        try:
            style_map = load_style_map(args.style_map)
        except (FileNotFoundError, ValueError) as exc:
            log.error("스타일 매핑 로드 실패: %s", exc)
            return 3

        if args.dry_run:
            return _run_dry_run(input_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="mapsi-") as work_dir:
            log.debug("work_dir: %s", work_dir)
            try:
                md_to_hwpx(
                    md_path=input_path,
                    output_path=output_path,
                    style_map=style_map,
                    work_dir=work_dir,
                )
            except NotImplementedError as exc:
                log.error("아직 지원되지 않는 변환 요소가 있음: %s", exc)
                return 4
            except Exception as exc:
                if args.verbose:
                    log.exception("변환 실패")
                else:
                    log.error("변환 실패: %s", exc)
                return 1

        log.info("변환 완료: %s", output_path)
        return 0
    finally:
        if previous_no_llm is None:
            os.environ.pop("MAPSI_NO_LLM", None)
        else:
            os.environ["MAPSI_NO_LLM"] = previous_no_llm


def _run_dry_run(input_path: Path) -> int:
    from .ast_walker import walk
    from .parser import parse_markdown

    blocks = parse_markdown(input_path)
    walked = walk(blocks)

    role_counts = Counter(
        getattr(block, "role", type(block).__name__) for block in walked
    )

    print(f"블록 수: {len(walked)}")
    for role, count in sorted(role_counts.items()):
        print(f"{role}: {count}")

    return 0


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
