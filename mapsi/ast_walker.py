"""Block 트리 순회와 문맥 의존 규칙 적용.

본 모듈의 책임은 ``parser`` 가 만든 Block 트리를 받아 다음 규칙을 일괄
적용한 트리를 반환하는 것이다.

규칙 1) 표 캡션 승격
    - 표 직전의 단락이 정규식 ``^(표|Table)\\s+\\d+\\.\\s*`` 로 시작하면
      해당 단락을 표 Block 의 ``meta["caption"]`` 으로 흡수하고 접두사를
      제거한다. 직전 단락은 평탄 리스트에서 제거된다.
      근거: docs/decisions/0001-table-caption-promotion.md

규칙 2) 그림 캡션 승격
    - 그림 Block 의 **직후** 단락이 ``^(그림|Figure)\\s+\\d+\\.\\s*`` 로
      시작하면 해당 단락을 그림 Block 의 ``meta["caption"]`` 으로 흡수하고
      접두사를 제거한다. 위치는 표와 반대이며 (표=직전, 그림=직후), 같은
      ADR 0001 의 일반화된 캡션 승격 정책을 따른다.

규칙 3) 참고문헌 섹션 감지 (후속)
    - 헤딩 텍스트가 "참고문헌" 또는 "References" 와 일치하면 그 이후의
      평문 단락들의 역할을 ``reference`` 로 변경한다 (다음 헤딩까지).

규칙 4) 각주 본문 흡수
    - ``role="footnote_def"`` Block 들을 모아 ``footnote_id`` 키로 색인한 뒤,
      본문 paragraph 의 ``meta["footnote_marks"]`` 항목 각각에 매칭되는
      ``text`` 를 채워 넣는다 (``mark["text"] = "각주 본문"``). 정의 Block
      자체는 출력 리스트에서 *제거* 된다 (한/글에서 각주 본문은 본문 안의
      ``hp:footNote`` 노드로 임베드되며 별도 단락이 아님).
    - 매칭되는 정의가 없는 마크는 ``mark["text"] = ""`` 로 두어 빌더가
      빈 각주를 emit 하도록 한다 (마크다운 작성 실수 방어).
    - 본 규칙은 표/그림 캡션 승격과 독립 — 어떤 순서로 적용해도 결과는
      동일하므로 마지막에 한 번 수행한다.
"""

from __future__ import annotations

import re
from copy import deepcopy

from .parser import Block


__all__ = ["walk", "TABLE_CAPTION_PATTERN", "FIGURE_CAPTION_PATTERN"]


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

FIGURE_CAPTION_PATTERN = re.compile(r"^(그림|Figure)\s+\d+\.\s*")
"""그림 캡션 승격 정규식. 형태는 :data:`TABLE_CAPTION_PATTERN` 과 동일하되
접두사가 ``표|Table`` 대신 ``그림|Figure``. ADR 0001 의 일반화 적용.
"""


def walk(blocks: list[Block]) -> list[Block]:
    """Block 트리를 순회하며 문맥 의존 규칙을 적용한 새 리스트를 반환한다.

    원본 ``blocks`` 는 변형하지 않고 순수 함수로 동작한다.

    적용 순서:
        1) 표 캡션 승격 (직전 단락 → 표 ``meta["caption"]``)
        2) 그림 캡션 승격 (직후 단락 → 그림 ``meta["caption"]``)
        3) 각주 본문 흡수 (footnote_def → paragraph mark["text"])

    각 규칙은 서로 다른 Block 역할을 다루므로 순서 상관없이 동일한 결과를
    산출한다. 현 구현은 표 → 그림 → 각주 순.
    """
    out = _promote_table_captions(blocks)
    out = _promote_figure_captions(out)
    out = _absorb_footnote_defs(out)
    return out


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


def _promote_figure_captions(blocks: list[Block]) -> list[Block]:
    """규칙 2 — 그림 직후의 단락이 캡션 패턴이면 그림에 흡수.

    표와 달리 lookahead 스캔. ``figure`` Block 을 만나면 그 다음 Block 이
    paragraph 이고 :data:`FIGURE_CAPTION_PATTERN` 매치인지 확인한다. 매치
    & 접두사 제거 후 텍스트가 비어있지 않으면, 그림 Block 의
    ``meta["caption"]`` 에 정제 텍스트를 채우고 다음 Block 은 출력에서
    건너뛴다 (소비). 이미 캡션이 설정된 그림은 변경하지 않는다 (멱등).

    원본 그림 Block 은 보존을 위해 ``deepcopy`` 후 수정.
    """
    out: list[Block] = []
    i = 0
    n = len(blocks)
    while i < n:
        blk = blocks[i]
        if (
            blk.role == "figure"
            and not blk.meta.get("caption")
            and i + 1 < n
        ):
            nxt = blocks[i + 1]
            caption = _try_extract_caption(nxt, FIGURE_CAPTION_PATTERN)
            if caption is not None:
                fig = deepcopy(blk)
                fig.meta["caption"] = caption
                out.append(fig)
                i += 2
                continue
        out.append(blk)
        i += 1
    return out


def _absorb_footnote_defs(blocks: list[Block]) -> list[Block]:
    """규칙 4 — ``footnote_def`` Block 의 본문을 본문 마크에 병합.

    1단계: 모든 ``footnote_def`` 를 한 번 훑어 ``footnote_id`` → ``text``
    사전을 만든다. 같은 id 가 두 번 나오면 *처음* 정의를 채택한다 (= 본문
    안에서 해당 라벨을 처음 정의한 것이 우선; 마크다운 plugin 도 동일
    방향). 2단계: 각 paragraph 의 ``meta["footnote_marks"]`` 항목에 매칭
    텍스트를 ``mark["text"]`` 로 채워 넣는다 (해당 id 에 정의가 없으면
    빈 문자열). 3단계: 출력 리스트에서 ``footnote_def`` Block 들은 제외.

    원본 Block 의 ``meta`` 보호를 위해, 마크가 있는 paragraph 만
    ``deepcopy`` 한다.
    """
    defs_by_id: dict[int, str] = {}
    for blk in blocks:
        if blk.role != "footnote_def":
            continue
        fid = blk.meta.get("footnote_id")
        if fid is None or fid in defs_by_id:
            continue
        defs_by_id[int(fid)] = blk.text

    out: list[Block] = []
    for blk in blocks:
        if blk.role == "footnote_def":
            continue
        marks = blk.meta.get("footnote_marks") if blk.meta else None
        if not marks:
            out.append(blk)
            continue
        new_blk = deepcopy(blk)
        for mark in new_blk.meta["footnote_marks"]:
            fid = mark.get("footnote_id")
            mark["text"] = defs_by_id.get(int(fid), "") if fid is not None else ""
        out.append(new_blk)
    return out


def _try_extract_caption(block: Block, pattern: re.Pattern[str]) -> str | None:
    """``block`` 이 paragraph 이고 ``pattern`` 에 매치하면 정제 텍스트 반환.

    표/그림 캡션 모두에 사용 가능한 공용 헬퍼. 접두사 제거 후 빈 문자열이
    되는 경우 (e.g. "그림 1." 단독) 는 캡션으로 보지 않고 ``None`` 반환.
    """
    if block.role != "paragraph":
        return None
    match = pattern.match(block.text)
    if match is None:
        return None
    caption = block.text[match.end() :].strip()
    if not caption:
        return None
    return caption


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
