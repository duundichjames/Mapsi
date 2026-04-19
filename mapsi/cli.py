"""CLI 엔트리포인트 (계약 5, C 영역).

C 부재 기간 동안 B 가 임시 구현. argparse 기반 단순 인터페이스이며,
work_dir 은 호출자가 만들고 정리한다 (계약 0.2 의 수명주기 규약).
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
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
    parser.add_argument("-o", "--output", required=True,
                        help="출력 HWPX 파일 경로")
    parser.add_argument("--style-map", default=str(_DEFAULT_STYLE_MAP),
                        help=f"스타일 매핑 YAML 경로 (기본: {_DEFAULT_STYLE_MAP})")
    parser.add_argument("--no-llm", action="store_true",
                        help="수식 변환에서 LLM 호출을 비활성화 (폴백만 사용)")
    parser.add_argument("--dry-run", action="store_true",
                        help="HWPX 파일을 쓰지 않고 변환 단계만 실행")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="상세 로그 출력")
    parser.add_argument("--version", action="version",
                        version=f"mapsi {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    from .config import load_style_map
    from .converter import md_to_hwpx

    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("mapsi.cli")

    _load_dotenv_if_available()

    if args.no_llm:
        import os
        os.environ["MAPSI_NO_LLM"] = "1"

    style_map = load_style_map(args.style_map)
    log.debug("스타일 매핑 로드 완료: %s", args.style_map)

    with tempfile.TemporaryDirectory(prefix="mapsi-") as work_dir:
        log.debug("work_dir: %s", work_dir)
        if args.dry_run:
            log.info("dry-run: 변환만 수행하고 출력 파일은 쓰지 않음")
            from .parser import parse_markdown
            from .ast_walker import walk
            from .builder.section import build_section
            blocks = parse_markdown(args.input)
            walked = walk(blocks)
            build_section(walked, style_map)
            return 0
        md_to_hwpx(args.input, args.output, style_map, work_dir)

    log.info("변환 완료: %s", args.output)
    return 0


def _load_dotenv_if_available() -> None:
    """``.env`` 파일에서 환경 변수를 로드 (python-dotenv 가 있을 때만).

    ``mapsi[llm]`` extras 를 설치한 경우에만 ``python-dotenv`` 가 들어
    있으므로, ImportError 시 조용히 skip 한다 (LLM 안 쓰는 사용자에게
    의존성을 강요하지 않음).

    동작 규약:

    * **프로젝트의 ``.env`` 가 셸 환경보다 우선한다** (``override=True``).
      Mapsi 는 CLI 도구이므로 "해당 프로젝트가 명시한 키" 가 권위 있어야
      하고, 셸에 미리 export 된 다른 도구용 키 (예: OpenAI 호환 엔드포인트
      뒤에 숨긴 Gemini 키) 와 섞이면 안 된다.

    * 안전망: ``.env`` 가 ``OPENAI_API_KEY`` 를 정의하지만
      ``OPENAI_API_BASE`` / ``OPENAI_BASE_URL`` 은 정의하지 않은 경우,
      셸에 미리 박혀 있던 base URL 변수들을 제거한다. 그러지 않으면
      진짜 OpenAI 키로 비-OpenAI 엔드포인트를 때리는 사고가 난다.
    """
    import os

    try:
        from dotenv import dotenv_values, find_dotenv, load_dotenv  # type: ignore
    except ImportError:
        return

    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        return

    env_values = dotenv_values(dotenv_path)
    load_dotenv(dotenv_path, override=True)

    if env_values.get("OPENAI_API_KEY"):
        for var in ("OPENAI_API_BASE", "OPENAI_BASE_URL"):
            if var not in env_values and var in os.environ:
                del os.environ[var]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
