"""골든 회귀 테스트용 헬퍼.

`tests/golden/<NN_name>/expected.yaml` 의 기대값과, `mapsi` 가
실제로 생성한 .hwpx 의 본문 단락 시퀀스를 정규화해 비교한다.

핵심 함수
---------

- :func:`extract_paragraph_sequence` -- .hwpx 1 개를 받아
  ``[(스타일이름, 텍스트), ...]`` 시퀀스를 반환.
- :func:`load_expected` -- ``expected.yaml`` 을 dict 로 로드.

비교 대상이 ``styleIDRef`` 의 raw 정수가 아니라 그 ID 가 가리키는
스타일 이름인 이유는 README.md 의 "비교 메커니즘" 섹션 참조.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml
from lxml import etree


HWPML_PARA_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HWPML_HEAD_NS = "http://www.hancom.co.kr/hwpml/2011/head"
HWPML_SECTION_NS = "http://www.hancom.co.kr/hwpml/2011/section"

NS = {
    "hp": HWPML_PARA_NS,
    "hh": HWPML_HEAD_NS,
    "hs": HWPML_SECTION_NS,
}


@dataclass(frozen=True)
class ParagraphInfo:
    """본문 단락 1 개의 비교 정보."""

    style_name: str
    text: str


def load_expected(fixture_dir: Path) -> dict:
    """``<fixture_dir>/expected.yaml`` 을 로드한다."""
    yaml_path = fixture_dir / "expected.yaml"
    with yaml_path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def _build_style_id_to_name(header_xml: bytes) -> dict[str, str]:
    """``header.xml`` 의 ``hh:style`` 정의에서 ``id -> name`` 매핑을 만든다.

    HWPX header.xml 의 스타일 노드는 다음과 같은 형태:

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
    """``hp:p`` 1 개에서 본문 텍스트를 결합한다.

    ``hp:run > hp:t`` 노드들의 텍스트를 순서대로 이어 붙임.
    포맷팅(굵게/기울임 등) 은 무시하고 평문만 추출.
    """
    parts: list[str] = []
    for t_node in p_element.iter(f"{{{HWPML_PARA_NS}}}t"):
        if t_node.text:
            parts.append(t_node.text)
    return "".join(parts)


def extract_paragraph_sequence(hwpx_path: Path) -> list[ParagraphInfo]:
    """``.hwpx`` 파일에서 본문 단락 시퀀스를 (스타일이름, 텍스트) 로 추출한다.

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
    빈 단락 처리 정책은 호출자가 결정.
    """
    with zipfile.ZipFile(hwpx_path, "r") as zf:
        header_bytes = zf.read("Contents/header.xml")
        section_bytes = zf.read("Contents/section0.xml")

    style_map = _build_style_id_to_name(header_bytes)
    section_root = etree.fromstring(section_bytes)

    results: list[ParagraphInfo] = []
    for p in section_root.iter(f"{{{HWPML_PARA_NS}}}p"):
        sid = p.get("styleIDRef", "")
        style_name = style_map.get(sid, f"<unknown:{sid}>")
        text = _extract_paragraph_text(p)
        results.append(ParagraphInfo(style_name=style_name, text=text))
    return results


def filter_nonempty(seq: Iterable[ParagraphInfo]) -> list[ParagraphInfo]:
    """텍스트가 빈 단락을 제외한 시퀀스를 반환한다.

    골든 비교에서는 보통 의미 단락만 대조한다. 빈 단락은 한/글이
    문서 끝에 자동 삽입하는 마지막 ``hp:p`` 같은 부산물일 수 있음.
    """
    return [info for info in seq if info.text != ""]
