"""마크다운 파싱.

markdown-it-py 의 토큰 스트림을 Mapsi 의 중간 표현인 ``Block`` 평탄 리스트로
재구성한다. 본 모듈은 토큰 → Block 변환에만 집중하며, 표/그림 캡션
승격이나 참고문헌 섹션 감지 등의 문맥 의존 규칙은 ``ast_walker`` 가 담당한다.

지원 토큰 (점진 추가):
    - ``paragraph_open`` / ``paragraph_close`` -- ``role="paragraph"``
    - ``heading_open`` / ``heading_close`` (h1~h6) -- ``role="heading"``,
      ``depth=1..6``

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


def _tokens_to_blocks(tokens: list[Token]) -> list[Block]:
    """markdown-it 토큰 스트림을 평탄 Block 리스트로 변환한다."""
    blocks: list[Block] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]

        if tok.type == "paragraph_open":
            inline_tok = tokens[i + 1]
            text = _inline_to_text(inline_tok)
            blocks.append(Block(role="paragraph", text=text))
            i += 3  # paragraph_open, inline, paragraph_close
            continue

        if tok.type == "heading_open":
            depth = int(tok.tag[1:])  # 'h1' -> 1
            inline_tok = tokens[i + 1]
            text = _inline_to_text(inline_tok)
            blocks.append(Block(role="heading", depth=depth, text=text))
            i += 3
            continue

        raise NotImplementedError(
            f"마크다운 토큰 {tok.type!r} 은 아직 지원되지 않는다 "
            f"(다음 픽스처에서 추가). 위치 line={tok.map}"
        )

    return blocks


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
