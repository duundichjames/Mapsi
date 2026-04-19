"""마크다운 파싱.

markdown-it-py 의 토큰 스트림을 Mapsi 의 중간 표현인 ``Block`` 평탄 리스트로
재구성한다. 본 모듈은 토큰 → Block 변환에만 집중하며, 표/그림 캡션
승격이나 참고문헌 섹션 감지 등의 문맥 의존 규칙은 ``ast_walker`` 가 담당한다.

지원 토큰 (점진 추가):
    - ``paragraph_open`` / ``paragraph_close`` -- ``role="paragraph"``
      (단, blockquote 내부에서는 ``role="blockquote"`` 로 승격)
    - ``heading_open`` / ``heading_close`` (h1~h6) -- ``role="heading"``,
      ``depth=1..6``
    - ``bullet_list_open`` / ``bullet_list_close`` + ``list_item_open`` /
      ``list_item_close`` -- ``role="bullet_list"``, ``depth=1..N``
    - ``ordered_list_open`` / ``ordered_list_close`` + 동일 -- ``role="ordered_list"``
    - ``blockquote_open`` / ``blockquote_close`` -- 컨테이너로만 동작.
      안의 ``paragraph_open`` 이 ``role="blockquote"`` Block 을 emit
    - ``fence`` / ``code_block`` -- 코드 블록 1 줄 = 1 Block
      (``role="code_block"``). 코드 안의 빈 줄도 1 Block 으로 보존.

지원되지 않는 토큰을 만나면 :class:`NotImplementedError` 를 발생시켜
조용한 데이터 손실을 방지한다 (다음 픽스처에서 명시적으로 추가).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token


__all__ = ["Block", "parse_markdown"]


@dataclass
class Block:
    """파서가 빌더에 전달하는 중간 표현 단위.

    Attributes:
        role: 블록의 의미 역할. ``spec/styles.yaml`` 의 최상위 키와 동일한
            영문 snake_case 키를 사용한다 (예: ``"paragraph"``,
            ``"heading"``, ``"bullet_list"``, ``"ordered_list"``,
            ``"blockquote"``, ``"code_block"``, ``"table"``,
            ``"figure"``, ``"footnote"``, ``"reference"``,
            ``"inline_equation"``, ``"display_equation"``).
        depth: 헤딩 레벨이나 목록 들여쓰기 깊이. 의미 없는 블록은 ``0``.
        text: 평문 본문이 있는 블록의 텍스트 (인라인 토큰 펼친 형태).
            인라인 서식은 ``children`` 에 별도 보관되며, 이 필드는
            서식 정보 없는 평문이다.
        children: 하위 Block 또는 인라인 노드 리스트.
        meta: 부가 정보. 표의 cell 배열, 코드블록의 ``info`` 문자열,
            이미지의 ``src``/``alt``, 각주 라벨 등 역할별 자유 슬롯.
    """

    role: str
    depth: int = 0
    text: str = ""
    children: list["Block"] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def parse_markdown(md_path: str | Path) -> list[Block]:
    """마크다운 파일을 읽어 평탄 Block 리스트로 파싱한다.

    Args:
        md_path: 입력 ``.md`` 파일 경로.

    Returns:
        문서 순서대로 정렬된 Block 리스트 (평탄 구조).
    """
    text = Path(md_path).read_text(encoding="utf-8")
    text = _strip_front_matter(text)
    md = MarkdownIt("commonmark")
    tokens = md.parse(text)
    return _tokens_to_blocks(tokens)


def _strip_front_matter(text: str) -> str:
    """선행 YAML front matter 가 있으면 제거하여 본문만 반환한다.

    front matter 가 없으면 입력을 그대로 반환.
    형식: 첫 줄이 정확히 ``---`` 이고, 이후 어딘가에 단독 ``---`` 가
    다시 등장하면 그 사이를 메타로 간주.
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return text
    if lines[0].strip() != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[i + 1 :])
    return text


_LIST_OPEN_TO_ROLE = {
    "bullet_list_open": "bullet_list",
    "ordered_list_open": "ordered_list",
}
_LIST_CLOSE_OF = {
    "bullet_list_open": "bullet_list_close",
    "ordered_list_open": "ordered_list_close",
}
_LIST_OPEN_TYPES = frozenset(_LIST_OPEN_TO_ROLE)
_LIST_CLOSE_TYPES = frozenset(_LIST_CLOSE_OF.values())


def _tokens_to_blocks(tokens: list[Token]) -> list[Block]:
    """markdown-it 토큰 스트림을 평탄 Block 리스트로 변환한다.

    목록은 중첩 가능하므로 ``list_stack`` 으로 현재 어떤 타입의 목록
    안에 있는지와 깊이를 추적한다 (스택 길이 = 깊이). 평탄 출력 전략 (Q1
    답변 (A) 평탄) 에 따라 각 list_item 은 자기 깊이만 ``Block.depth`` 에
    실어 동일 레벨로 emit 한다.
    """
    blocks: list[Block] = []
    list_stack: list[str] = []  # "bullet_list" or "ordered_list"
    blockquote_depth = 0
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        if tok.type == "heading_open":
            depth = int(tok.tag[1:])
            text = _inline_to_text(tokens[i + 1])
            blocks.append(Block(role="heading", depth=depth, text=text))
            i += 3
            continue

        if tok.type == "paragraph_open":
            text = _inline_to_text(tokens[i + 1])
            if blockquote_depth > 0:
                blocks.append(Block(role="blockquote", text=text))
            elif not list_stack:
                blocks.append(Block(role="paragraph", text=text))
            # list 안의 paragraph 는 list_item_open 시점에 이미 처리됨
            i += 3
            continue

        if tok.type in _LIST_OPEN_TYPES:
            list_stack.append(_LIST_OPEN_TO_ROLE[tok.type])
            i += 1
            continue

        if tok.type in _LIST_CLOSE_TYPES:
            if not list_stack:
                raise ValueError(
                    f"닫는 list 토큰 {tok.type!r} 이 짝 없이 등장 (위치 line={tok.map})"
                )
            list_stack.pop()
            i += 1
            continue

        if tok.type == "list_item_open":
            if not list_stack:
                raise ValueError(
                    f"list_item_open 이 list 컨테이너 밖에서 등장 (위치 line={tok.map})"
                )
            role = list_stack[-1]
            depth = len(list_stack)
            text = _first_inline_text_in_item(tokens, i)
            blocks.append(Block(role=role, depth=depth, text=text))
            i += 1
            continue

        if tok.type == "list_item_close":
            i += 1
            continue

        if tok.type == "blockquote_open":
            blockquote_depth += 1
            i += 1
            continue

        if tok.type == "blockquote_close":
            if blockquote_depth <= 0:
                raise ValueError(
                    f"blockquote_close 가 짝 없이 등장 (위치 line={tok.map})"
                )
            blockquote_depth -= 1
            i += 1
            continue

        if tok.type in ("fence", "code_block"):
            blocks.extend(_emit_code_lines(tok))
            i += 1
            continue

        raise NotImplementedError(
            f"마크다운 토큰 {tok.type!r} 은 아직 지원되지 않는다 "
            f"(다음 픽스처에서 추가). 위치 line={tok.map}"
        )

    if list_stack:
        raise ValueError(f"닫히지 않은 list 컨테이너가 남음: {list_stack}")
    if blockquote_depth != 0:
        raise ValueError(f"닫히지 않은 blockquote 가 {blockquote_depth} 개 남음")
    return blocks


def _emit_code_lines(code_tok: Token) -> list[Block]:
    """``fence`` / ``code_block`` 토큰을 줄 단위 Block 리스트로 펼친다.

    한/글의 "코드" 스타일은 단락 단위로 적용되므로 코드 1 줄을
    1 Block 으로 매핑한다 (Q1 답 (A) 평탄과 일관). markdown-it 의 ``fence``
    토큰은 본문 끝에 항상 ``"\\n"`` 을 붙여 두므로 마지막 1개의 trailing
    개행만 제거하고 split 한다. 빈 줄은 텍스트 빈 Block 으로 보존한다.

    Code fence 의 ``info`` (언어 힌트, 예: ``python``) 는 첫 Block 의
    ``meta["info"]`` 에 기록한다. 후속 픽스처에서 신택스 하이라이트나
    캡션 표기로 활용 여지를 남긴다.
    """
    content = code_tok.content or ""
    if content.endswith("\n"):
        content = content[:-1]
    lines = content.split("\n") if content else [""]
    blocks: list[Block] = [Block(role="code_block", text=line) for line in lines]
    info = (code_tok.info or "").strip()
    if info and blocks:
        blocks[0].meta["info"] = info
    return blocks


def _first_inline_text_in_item(tokens: list[Token], item_open_idx: int) -> str:
    """``list_item_open`` 직후의 첫 inline 텍스트를 반환한다.

    중첩 list 가 시작되거나 ``list_item_close`` 를 만나면 그 이전까지만
    훑는다 (= 자기 자신의 텍스트만 가져오고 중첩 항목 텍스트는 무시).
    항목이 비어있거나 텍스트 없는 항목이면 빈 문자열 반환.
    """
    j = item_open_idx + 1
    while j < len(tokens):
        t = tokens[j]
        if t.type == "list_item_close" or t.type in _LIST_OPEN_TYPES:
            return ""
        if t.type == "inline":
            return _inline_to_text(t)
        j += 1
    return ""


def _inline_to_text(inline_tok: Token) -> str:
    """``inline`` 토큰의 자식들에서 평문을 추출한다.

    굵게/기울임/링크 등의 인라인 서식은 무시하고 텍스트 컨텐츠만 모은다
    (인라인 서식 처리는 후속 픽스처에서 추가).
    """
    if inline_tok.type != "inline" or inline_tok.children is None:
        return inline_tok.content or ""
    parts: list[str] = []
    for child in inline_tok.children:
        if child.type == "text":
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append("\n")
    return "".join(parts)
