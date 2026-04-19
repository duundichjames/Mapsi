"""마크다운 파싱.

markdown-it-py 의 토큰 스트림을 Mapsi 의 중간 표현인 ``Block`` 트리로
재구성한다. 본 모듈은 토큰 → Block 트리 변환에만 집중하며, 표/그림 캡션
승격이나 참고문헌 섹션 감지 등의 문맥 의존 규칙은 ``ast_walker`` 가 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    """마크다운 파일을 읽어 Block 트리로 파싱한다.

    Args:
        md_path: 입력 ``.md`` 파일 경로.

    Returns:
        문서 순서대로 정렬된 최상위 Block 리스트. 표나 목록처럼 구조를
        가진 블록의 자식은 ``children`` 에 들어간다.

    구현 메모:
        - GFM 활성화 (table, strikethrough)
        - 수식은 ``$...$`` / ``$$...$$`` 정규식으로 후처리하여
          ``inline_equation`` / ``display_equation`` 역할을 부여
        - YAML front matter 는 무시 (테스트 메타용이며 본문 아님)
    """
    raise NotImplementedError("parse_markdown 은 후속 커밋에서 구현된다")
