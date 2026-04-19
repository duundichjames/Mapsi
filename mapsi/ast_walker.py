"""Block 트리 순회와 문맥 의존 규칙 적용.

본 모듈의 책임은 ``parser`` 가 만든 Block 트리를 받아 다음 규칙을 일괄
적용한 트리를 반환하는 것이다.

규칙 1) 표 캡션 승격
    - 표 직전의 단락이 정규식 ``^(표|Table)\\s+\\d+\\.\\s*`` 로 시작하면
      해당 단락을 표 Block 의 ``meta["caption"]`` 으로 흡수하고 접두사를
      제거한다. 직전 단락은 평탄 리스트에서 제거된다.
      근거: docs/decisions/0001-table-caption-promotion.md

규칙 2) 그림 캡션 승격 (후속)
    - 그림(이미지) 직후의 단락이 ``^(그림|Figure)\\s+\\d+\\.\\s*`` 로
      시작하면 해당 단락을 ``figure_caption`` 으로 승격하고 접두사를 제거한다.

규칙 3) 참고문헌 섹션 감지 (후속)
    - 헤딩 텍스트가 "참고문헌" 또는 "References" 와 일치하면 그 이후의
      평문 단락들의 역할을 ``reference`` 로 변경한다 (다음 헤딩까지).

규칙 4) 각주 정의 분리 (후속)
    - ``[^N]: ...`` 정의를 본문에서 떼어 별도 ``footnote`` 블록으로 만든다.
"""

from __future__ import annotations

import re
from copy import deepcopy

from .parser import Block


__all__ = ["walk", "TABLE_CAPTION_PATTERN"]


TABLE_CAPTION_PATTERN = re.compile(r"^(표|Table)\s+\d+\.\s*")
"""표 캡션 승격에 쓰는 정규식 (ADR 0001).

매치 시 그룹은 의미 있는 캡쳐를 하지 않으며, ``re.sub`` 로 접두사 제거에만
사용한다. 매치 조건:

- 줄 시작에서 "표" 또는 "Table" (대소문자 구분)
- 그 뒤 1 글자 이상 공백
- 정수
- 마침표
- 0 글자 이상 공백 (캡션 본문 앞 공백 정규화)
"""


def walk(blocks: list[Block]) -> list[Block]:
    """Block 트리를 순회하며 문맥 의존 규칙을 적용한 새 리스트를 반환한다.

    원본 ``blocks`` 는 변형하지 않고 순수 함수로 동작한다.

    현 단계 구현: 규칙 1 (표 캡션 승격) 만 적용. 나머지 규칙은 후속
    픽스처에서 추가.
    """
    return _promote_table_captions(blocks)


def _promote_table_captions(blocks: list[Block]) -> list[Block]:
    """규칙 1 — 표 직전의 단락이 캡션 패턴이면 표에 흡수.

    한 번의 좌→우 스캔. 출력 리스트를 별도로 만들고, 표 Block 을 만나기
    직전에 마지막으로 추가한 Block 이 캡션 패턴인 paragraph 면 출력에서
    꺼내어 표의 ``meta["caption"]`` 에 넣는다. 이미 캡션이 설정된 표는
    건드리지 않는다 (멱등).

    원본 Block 의 ``meta`` 는 그대로 두기 위해 표 Block 만 ``deepcopy``
    한다.
    """
    out: list[Block] = []
    for blk in blocks:
        if blk.role == "table" and not blk.meta.get("caption"):
            promoted = _try_promote_previous(out)
            if promoted is not None:
                table = deepcopy(blk)
                table.meta["caption"] = promoted
                out.append(table)
                continue
        out.append(blk)
    return out


def _try_promote_previous(out: list[Block]) -> str | None:
    """``out`` 의 마지막 Block 이 캡션 패턴이면 제거하고 정제 텍스트 반환.

    승격 조건:
      - 마지막 Block 의 ``role == "paragraph"``
      - 텍스트가 :data:`TABLE_CAPTION_PATTERN` 에 매치
      - 매치 후 남는 텍스트가 비어있지 않음 (e.g. "표 1." 단독은 캡션 아님)

    조건을 만족하면 마지막 Block 을 ``out`` 에서 ``pop`` 하고 접두사 제거된
    텍스트를 반환한다. 그렇지 않으면 ``None`` 반환 (출력 변경 없음).
    """
    if not out:
        return None
    last = out[-1]
    if last.role != "paragraph":
        return None
    match = TABLE_CAPTION_PATTERN.match(last.text)
    if match is None:
        return None
    caption = last.text[match.end() :].strip()
    if not caption:
        return None
    out.pop()
    return caption
