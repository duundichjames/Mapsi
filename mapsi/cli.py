"""CLI 엔트리포인트 (계약 5, C 영역 본 구현 + B 의 ``.env`` 우선 정책 합성).

C 의 본 구현 (입력 파일 검증, 환경 변수 복원, 에러 코드 분리, dry-run 의
role counter 출력) 위에 B 가 도입한 두 가지를 보존한다.

* :func:`apply_project_dotenv` — 프로젝트 ``.env`` 가 셸 환경보다 우선
  (``override=True``). LLM 키가 셸에 박혀 있던 다른 도구용 키와 섞여
  401/403 사고가 나던 문제를 차단. CLI 와 Streamlit UI 가 공통으로
  쓸 수 있도록 퍼블릭으로 노출한다.
* dry-run 분기에서 ``build_section()`` 까지 호출 — styles.yaml 매핑 누락,
  figure src 누락 같은 빌드 단계 오류를 파일 쓰기 없이 검증한다.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import __version__


__all__ = ["main", "build_parser", "apply_project_dotenv"]


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
        help="출력 파일을 쓰지 않고 파싱/워크/빌드 단계까지 점검",
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

    apply_project_dotenv()

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
            return _run_dry_run(input_path, style_map, log)

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


def _run_dry_run(
    input_path: Path,
    style_map: dict,
    log: logging.Logger,
) -> int:
    """파일을 쓰지 않고 파싱→워크→빌드까지 검증한 뒤 role 분포 요약.

    빌드 단계 (``build_section``) 까지 호출하므로 styles.yaml 매핑 누락,
    figure src 누락, header.xml 정합성 오류 같은 문제도 dry-run 에서 잡힌다.
    """
    from .ast_walker import walk
    from .builder.header import parse_style_table
    from .builder.section import build_section
    from .parser import parse_markdown

    log.info("dry-run: 파싱→워크→빌드 단계 검증 (출력 파일 안 씀)")

    repo_root = Path(__file__).resolve().parents[1]
    base_section = (
        repo_root / "samples" / "base" / "unpacked" / "Contents" / "section0.xml"
    )
    header_bytes = (
        repo_root / "templates" / "Contents" / "header.xml"
    ).read_bytes()
    style_table = parse_style_table(header_bytes)

    blocks = parse_markdown(input_path)
    walked = walk(blocks)
    build_section(walked, style_map, style_table, base_section)

    role_counts = Counter(
        getattr(block, "role", type(block).__name__) for block in walked
    )

    print(f"블록 수: {len(walked)}")
    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")

    return 0


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def apply_project_dotenv() -> None:
    """프로젝트 ``.env`` 를 로드하고 셸 환경 변수를 덮어쓴다 (우선 정책).

    ``mapsi[llm]`` extras 를 설치한 경우에만 ``python-dotenv`` 가 들어
    있으므로, ImportError 시 조용히 skip 한다 (LLM 안 쓰는 사용자에게
    의존성을 강요하지 않음).

    동작 규약:

    * **프로젝트의 ``.env`` 가 셸 환경보다 우선한다** (``override=True``).
      Mapsi 는 CLI 및 Streamlit UI 도구이므로 "해당 프로젝트가 명시한 키"
      가 권위 있어야 하고, 셸에 미리 export 된 다른 도구용 키 (예: OpenAI
      호환 엔드포인트 뒤에 숨긴 Gemini 키) 와 섞이면 안 된다.
    * 안전망: ``.env`` 가 ``OPENAI_API_KEY`` 를 정의하지만
      ``OPENAI_API_BASE`` / ``OPENAI_BASE_URL`` 은 정의하지 않은 경우,
      셸에 미리 박혀 있던 base URL 변수들을 제거한다. 그러지 않으면
      진짜 OpenAI 키로 비-OpenAI 엔드포인트를 때리는 사고가 난다.

    양쪽 UI (CLI / Streamlit) 에서 동일 로직을 쓰도록 퍼블릭 함수로
    노출한다.
    """
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


_load_dotenv_if_available = apply_project_dotenv


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
