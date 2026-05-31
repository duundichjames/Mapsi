"""section0.xml 빌더.

Block 리스트(walker 통과본) 와 스타일 정보를 받아 완성된
``section0.xml`` 바이트열을 반환한다.

설계 메모 — secPr 의 보존
-------------------------

HWPX 의 ``hp:secPr`` (페이지 크기, 여백, 쪽번호, 각주, 페이지 테두리 등
문서 전역 속성) 은 첫 ``hp:p`` 의 첫 ``hp:run`` 안에 끼어 있는 비대칭
구조를 갖는다. 마크다운에는 이 정보를 만들어낼 입력이 없으므로,
변환기는 ``samples/base/unpacked/Contents/section0.xml`` 의 첫 ``hp:p``
를 통째로 가져와 secPr 만 보존하고 나머지(텍스트 런, lineseg) 는
초기화한 뒤, 그 다음에 우리 변환 결과 단락들을 이어 붙인다.

결과적으로 출력 section0.xml 은 다음 구조가 된다.

.. code-block:: xml

    <hs:sec>
      <hp:p ...>           ← secPr 호스트 (바탕글 스타일, 빈 텍스트)
        <hp:run>
          <hp:secPr> ... </hp:secPr>
          <hp:ctrl/>
        </hp:run>
      </hp:p>
      <hp:p ...> ... </hp:p>   ← 우리 첫 블록
      <hp:p ...> ... </hp:p>   ← 우리 둘째 블록
      ...
    </hs:sec>

여분의 빈 단락 1 개가 문서 맨 앞에 들어가지만, 이는 회귀 테스트의
``filter_nonempty()`` 에 의해 비교에서 제외되며, 한/글에서는 한 줄
공백으로 표시된다. 향후 마크다운 문서 자체에 secPr 메타가 정의될
가능성을 열어두기 위해 이 호스트 단락을 별도로 보존하는 전략을 택했다.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from lxml import etree

from ..parser import Block
from .elements import (
    UnsupportedFeature,
    build_figure_caption_paragraph,
    build_figure_paragraph,
    build_paragraph,
    build_table_wrapper,
    build_unsupported_marker,
)
from .header import StyleEntry


__all__ = ["build_section"]


HWPML_PARA_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
_HP = f"{{{HWPML_PARA_NS}}}"


def build_section(
    blocks: list[Block],
    style_map: dict[str, Any],
    style_table: dict[str, StyleEntry],
    base_section_path: str | Path,
    image_map: dict[str, dict] | None = None,
) -> bytes:
    """Block 리스트를 받아 완성된 section0.xml 바이트열을 반환한다.

    Parameters
    ----------
    blocks:
        ``ast_walker.walk()`` 의 출력. 평탄 Block 리스트.
    style_map:
        ``config.load_style_map()`` 의 반환 딕셔너리.
    style_table:
        ``builder.header.parse_style_table()`` 의 반환 딕셔너리.
    base_section_path:
        secPr 추출 원본인 ``samples/base/unpacked/Contents/section0.xml``
        경로. 이 파일의 첫 ``hp:p`` 가 secPr 호스트로 사용된다.
    image_map:
        figure 의 ``src`` 문자열 → ``{binary_item_id, width_hwpunit,
        height_hwpunit}`` 매핑 (``converter._register_figure_images`` 가
        구성). None 이면 figure 들은 Phase 6a placeholder 모드로 emit
        된다 (이미지 없음, alt 텍스트만). 단위 테스트 호환을 위해 옵션.

    Returns
    -------
    bytes
        ``<?xml ...?>`` 선언으로 시작하는 완전한 XML 바이트열.
        UTF-8 인코딩, standalone="yes".
    """
    image_map = image_map or {}
    base_tree = etree.parse(str(base_section_path))
    new_root = base_tree.getroot()

    # 1. base 의 모든 단락 중 첫 번째만 secPr 호스트로 보존, 나머지는 제거.
    children = list(new_root)
    if not children:
        raise ValueError(
            f"base section0.xml 이 비어 있음: {base_section_path}"
        )
    secpr_host = children[0]
    for child in children[1:]:
        new_root.remove(child)

    # 2. 호스트 단락에서 텍스트 런과 lineseg 만 제거하고 secPr 보유 런만 남긴다.
    _strip_text_content(secpr_host)

    # 3. 우리 변환 결과 블록들을 호스트 단락 뒤에 순서대로 추가.
    #    role 별 dispatch:
    #      - table:  wrapper paragraph 안에 hp:tbl + (선택) caption
    #      - figure: image_map 에 src 가 있으면 hp:pic 끼운 단일 hp:p
    #                (캡션도 그 안의 hp:caption 으로 흡수). 없으면 Phase 6a
    #                placeholder 모드 (그림 단락 + 별도 그림캡션 단락).
    #      - 그 외:  단순 hp:p 1 개로 매핑
    # 헤딩 앞 빈 줄(항목 2) 의 "첫 헤딩 제외" 판정용. front matter 의
    # title/author/date 는 본문 내용으로 치지 않으므로, 그 뒤 첫 헤딩 앞에는
    # 빈 줄을 넣지 않는다. 실제 내용(본문/표/그림/헤딩 등) 이 한 번이라도
    # emit 된 뒤의 헤딩 앞에만 빈 줄을 넣는다.
    front_matter_roles = {"doc_title", "doc_author", "doc_date"}
    seen_content = False
    for block in blocks:
        # 의도된 미지원(UnsupportedFeature) 만 잡아 그 블록을 표식 단락으로
        # 대체하고 계속한다. 그 밖의 예외(KeyError·ValueError·파서의 일반
        # NotImplementedError 등) 는 전파해 실제 버그가 드러나게 한다.
        # 상위 타입 NotImplementedError 가 아니라 UnsupportedFeature 만 잡는다.
        try:
            # 항목 2 — 헤딩 앞 빈 줄 (단, 문서 첫 헤딩 앞에는 넣지 않음).
            if block.role == "heading" and seen_content:
                new_root.append(_build_blank_paragraph(style_map, style_table))
            if block.role == "table":
                new_root.append(
                    build_table_wrapper(block, style_map, style_table)
                )
                # 항목 1 — 표 뒤 빈 줄 (표와 다음 서술 사이 간격).
                new_root.append(_build_blank_paragraph(style_map, style_table))
            elif block.role == "figure":
                src = block.meta.get("src") if block.meta else None
                image_info = image_map.get(src) if src else None
                new_root.append(
                    build_figure_paragraph(
                        block, style_map, style_table, image_info=image_info
                    )
                )
                # placeholder 모드에서만 별도 캡션 단락 추가 (Phase 6a 호환).
                # hp:pic 모드에서는 캡션이 hp:pic 내부로 들어갔으므로 중복 금지.
                caption = block.meta.get("caption")
                if image_info is None and caption:
                    new_root.append(
                        build_figure_caption_paragraph(
                            str(caption), style_map, style_table
                        )
                    )
            else:
                new_root.append(
                    build_paragraph(block, style_map, style_table)
                )
        except UnsupportedFeature:
            new_root.append(
                build_unsupported_marker(block.text, style_map, style_table)
            )
        if block.role not in front_matter_roles:
            seen_content = True

    return etree.tostring(
        new_root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def _build_blank_paragraph(
    style_map: dict[str, Any], style_table: dict[str, StyleEntry]
) -> etree._Element:
    """빈 본문 단락(``hp:p``, 본문 스타일) 1 개를 만든다 — 간격용 빈 줄.

    표 뒤(항목 1)·헤딩 앞(항목 2) 에 한 줄 간격을 주기 위한 빈 단락. 본문
    스타일을 그대로 쓰며 텍스트는 비어 있다.
    """
    return build_paragraph(Block(role="paragraph", text=""), style_map, style_table)


def _strip_text_content(p_element: etree._Element) -> None:
    """secPr 호스트 단락에서 본문 콘텐츠를 제거한다.

    제거 대상:
        - secPr 를 보유한 첫 ``hp:run`` 이외의 모든 ``hp:run``
        - ``hp:linesegarray`` (한/글이 재생성)

    보존 대상:
        - secPr 를 보유한 첫 ``hp:run`` (그 안의 ``hp:secPr`` 와 ``hp:ctrl``
          은 원본 그대로)
    """
    runs = p_element.findall(f"{_HP}run")
    secpr_run = None
    for run in runs:
        if run.find(f"{_HP}secPr") is not None:
            secpr_run = run
            break

    for child in list(p_element):
        if child is secpr_run:
            continue
        p_element.remove(child)

    # secPr 호스트 run 내부에서도 텍스트 런 (hp:t) 은 제거. ctrl 만 남김.
    if secpr_run is not None:
        for t in secpr_run.findall(f"{_HP}t"):
            secpr_run.remove(t)
