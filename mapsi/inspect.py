"""HWPX 검사 도구 — 변환 결과가 의도대로인지 1초 안에 확인.

본 모듈은 두 역할을 동시에 한다:

- **라이브러리 API**: 다른 모듈이나 테스트가 ``.hwpx`` 의 본문 단락을
  ``ParagraphInfo`` 시퀀스로 추출하기 위한 진입점.
- **CLI 진입점**: ``python -m mapsi.inspect <hwpx>`` 로 사람이 읽기
  좋은 형태로 단락별 (스타일 이름, 텍스트) 를 출력. ``--styles`` 옵션은
  사용된 스타일 정의 요약과 정합성 검증까지 수행.

설계 노트
---------
한/글 뷰어(무료) 는 스타일 표시줄이 사실상 없어 변환 검증이 어렵다.
정품 한/글이 없어도 셸에서 빠르게 "스타일 이름 + 텍스트" 시퀀스를
대조할 수 있도록 본 도구가 필요하다. ``tests/_golden.py`` 가 사용하던
헬퍼들을 본 모듈로 승격하여 단일 진실원으로 통합했다.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from lxml import etree


__all__ = [
    "HWPML_PARA_NS",
    "HWPML_HEAD_NS",
    "HWPML_SECTION_NS",
    "ParagraphInfo",
    "extract_paragraph_sequence",
    "extract_style_id_to_name",
    "filter_nonempty",
    "main",
]


HWPML_PARA_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HWPML_HEAD_NS = "http://www.hancom.co.kr/hwpml/2011/head"
HWPML_SECTION_NS = "http://www.hancom.co.kr/hwpml/2011/section"


@dataclass(frozen=True)
class ParagraphInfo:
    """본문 단락 1 개의 검사 정보."""

    style_name: str
    style_id: str
    text: str


def extract_style_id_to_name(header_xml: bytes) -> dict[str, str]:
    """``header.xml`` 의 ``hh:style`` 정의에서 ``id -> name`` 매핑을 만든다.

    HWPX header.xml 의 스타일 노드는 다음과 같은 형태다:

    .. code-block:: xml

        <hh:style id="0" type="PARA" name="바탕글" engName="Normal" .../>
    """
    root = etree.fromstring(header_xml)
    mapping: dict[str, str] = {}
    for style in root.iter(f"{{{HWPML_HEAD_NS}}}style"):
        sid = style.get("id")
        name = style.get("name")
        if sid is None or name is None:
            continue
        mapping[sid] = name
    return mapping


def _extract_paragraph_text(p_element: etree._Element) -> str:
    """``hp:p`` 1 개에서 *자기 자신의* 본문 텍스트만 결합한다.

    ``hp:run > hp:t`` 노드들의 텍스트를 순서대로 이어 붙인다. 단, 다음
    경계 안의 후손 ``hp:t`` 는 *별도 ``hp:p`` 로 따로 열거되므로* 이중
    카운트 방지를 위해 제외한다:

    - ``hp:tbl``: 표 셀 안의 단락
    - ``hp:pic``: 그림 캡션 (``hp:pic > hp:caption > hp:subList > hp:p``)

    그림 단락 (``hp:pic`` 가 직접 자손에 있음) 은 본체에 텍스트가 없으므로
    검증 가시성을 위해 ``hp:pic > hp:shapeComment`` (대체 텍스트) 를 합성
    텍스트로 반환한다. shapeComment 가 비어 있으면 ``"[그림]"`` 자리표시.
    """
    pic_tag = f"{{{HWPML_PARA_NS}}}pic"
    tbl_tag = f"{{{HWPML_PARA_NS}}}tbl"
    parts: list[str] = []
    has_pic = False
    for t_node in p_element.iter(f"{{{HWPML_PARA_NS}}}t"):
        if not t_node.text:
            continue
        if _is_descendant_of_tag(t_node, p_element, tbl_tag):
            continue
        if _is_descendant_of_tag(t_node, p_element, pic_tag):
            continue
        parts.append(t_node.text)
    if not parts:
        # hp:pic 직속 자손이 있으면 alt 텍스트 (shapeComment) 를 노출.
        for pic in p_element.iter(pic_tag):
            has_pic = True
            comment = pic.find(f"{{{HWPML_PARA_NS}}}shapeComment")
            if comment is not None and comment.text:
                return comment.text
            break
        if has_pic:
            return "[그림]"
    return "".join(parts)


def _is_descendant_of_tag(
    node: etree._Element, ancestor_root: etree._Element, tag: str
) -> bool:
    """``node`` 가 ``ancestor_root`` 까지 거슬러 올라가는 사이 ``tag`` 를 만나는가."""
    cur = node.getparent()
    while cur is not None and cur is not ancestor_root:
        if cur.tag == tag:
            return True
        cur = cur.getparent()
    return False


def extract_paragraph_sequence(hwpx_path: str | Path) -> list[ParagraphInfo]:
    """``.hwpx`` 파일에서 본문 단락 시퀀스를 추출한다.

    Parameters
    ----------
    hwpx_path:
        검사할 HWPX (= ZIP) 파일.

    Returns
    -------
    list[ParagraphInfo]
        ``Contents/section0.xml`` 의 ``hp:p`` 들을 문서 순으로 열거하며,
        각각의 ``styleIDRef`` 를 같은 .hwpx 의 ``Contents/header.xml`` 에
        등록된 스타일 이름으로 변환한 결과.

    Notes
    -----
    같은 ``hp:p`` 라도 빈 단락(텍스트 0 자) 도 포함하여 반환한다.
    빈 단락 처리 정책은 호출자가 결정 (:func:`filter_nonempty` 참조).
    """
    with zipfile.ZipFile(hwpx_path, "r") as zf:
        header_bytes = zf.read("Contents/header.xml")
        section_bytes = zf.read("Contents/section0.xml")

    id_to_name = extract_style_id_to_name(header_bytes)
    section_root = etree.fromstring(section_bytes)

    results: list[ParagraphInfo] = []
    for p in section_root.iter(f"{{{HWPML_PARA_NS}}}p"):
        sid = p.get("styleIDRef", "")
        name = id_to_name.get(sid, f"<unknown:{sid}>")
        text = _extract_paragraph_text(p)
        results.append(ParagraphInfo(style_name=name, style_id=sid, text=text))
    return results


def filter_nonempty(seq: Iterable[ParagraphInfo]) -> list[ParagraphInfo]:
    """텍스트가 빈 단락을 제외한 시퀀스를 반환한다.

    골든 비교에서는 보통 의미 단락만 대조한다. 빈 단락은 한/글이
    문서 끝에 자동 삽입하는 마지막 ``hp:p`` 같은 부산물이거나,
    section0.xml 의 ``hp:secPr`` 호스트 단락일 수 있음.
    """
    return [info for info in seq if info.text != ""]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_table(rows: list[ParagraphInfo]) -> str:
    """단락 시퀀스를 정렬된 표로 포맷."""
    if not rows:
        return "  (본문 단락 없음)"
    name_width = max(len(r.style_name) for r in rows)
    name_width = max(name_width, 4)  # 최소폭
    lines: list[str] = []
    for i, info in enumerate(rows, 1):
        name = info.style_name.center(name_width)
        sid = f"id={info.style_id}".ljust(6)
        text = info.text if info.text else "(빈 단락)"
        lines.append(f"  {i:3d}. [{name}] {sid} {text}")
    return "\n".join(lines)


def _styles_summary(hwpx_path: Path) -> str:
    """``--styles`` 모드의 출력: 사용된 스타일 정의 요약 + 정합성 점검."""
    seq = extract_paragraph_sequence(hwpx_path)

    with zipfile.ZipFile(hwpx_path, "r") as zf:
        header_bytes = zf.read("Contents/header.xml")
    id_to_name = extract_style_id_to_name(header_bytes)

    used_ids = sorted({info.style_id for info in seq if info.style_id})
    lines = ["", "[사용된 스타일 정의]"]
    if not used_ids:
        lines.append("  (참조된 스타일 없음)")
    for sid in used_ids:
        name = id_to_name.get(sid, "<정의 없음>")
        lines.append(f"  styleIDRef={sid:<3s}  {name}")

    lines.append("")
    lines.append("[정합성]")
    missing = [sid for sid in used_ids if sid not in id_to_name]
    if missing:
        for sid in missing:
            offending = next(
                (i for i, info in enumerate(seq, 1) if info.style_id == sid),
                "?",
            )
            lines.append(
                f"  X styleIDRef={sid} 가 header.xml 에 정의되지 않음 "
                f"(첫 등장: 단락 #{offending})"
            )
    else:
        lines.append("  OK 모든 styleIDRef 가 header.xml 에 정의되어 있다")
    lines.append(
        f"  ㆍ 본문에 등장한 스타일 {len(used_ids)} 종 / "
        f"header.xml 의 스타일 정의 {len(id_to_name)} 종"
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mapsi.inspect",
        description=(
            "HWPX 파일을 풀어서 본문 단락별 (스타일 이름, 텍스트) 를 출력한다. "
            "한/글 없이도 변환 결과가 의도대로인지 셸에서 검증할 수 있다."
        ),
    )
    parser.add_argument(
        "paths", nargs="+", type=Path, help="검사할 .hwpx 파일들 (1 개 이상)"
    )
    parser.add_argument(
        "--styles",
        action="store_true",
        help="사용된 스타일 정의 요약 + 정합성 점검을 함께 출력",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="빈 단락(secPr 호스트 등) 도 포함하여 출력 (기본은 비-빈 단락만)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. ``python -m mapsi.inspect <hwpx>...`` 로 호출."""
    args = _build_parser().parse_args(argv)
    exit_code = 0
    for path in args.paths:
        if not path.exists():
            print(f"[오류] 파일이 없다: {path}", file=sys.stderr)
            exit_code = 2
            continue
        print(f"\n=== {path} ===")
        seq = extract_paragraph_sequence(path)
        if not args.all:
            seq = filter_nonempty(seq)
        print(_format_table(seq))
        if args.styles:
            print(_styles_summary(path))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
