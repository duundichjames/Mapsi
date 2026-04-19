"""Block 트리 순회와 문맥 의존 규칙 적용.

본 모듈의 책임은 ``parser`` 가 만든 Block 트리를 받아 다음 규칙을 일괄
적용한 트리를 반환하는 것이다.

규칙 1) 표 캡션 승격
    - 표 직전의 단락이 정규식 ``^(표|Table)\\s+\\d+\\.\\s*`` 로 시작하면
      해당 단락을 ``table_caption`` 으로 승격하고 접두사를 제거한다.

규칙 2) 그림 캡션 승격
    - 그림(이미지) 직후의 단락이 ``^(그림|Figure)\\s+\\d+\\.\\s*`` 로
      시작하면 해당 단락을 ``figure_caption`` 으로 승격하고 접두사를 제거한다.

규칙 3) 참고문헌 섹션 감지
    - 헤딩 텍스트가 "참고문헌" 또는 "References" 와 일치하면 그 이후의
      평문 단락들의 역할을 ``reference`` 로 변경한다 (다음 헤딩까지).

규칙 4) 각주 정의 분리
    - ``[^N]: ...`` 정의를 본문에서 떼어 별도 ``footnote`` 블록으로 만든다.
"""

from __future__ import annotations

from .parser import Block


__all__ = ["walk"]


def walk(blocks: list[Block]) -> list[Block]:
    """Block 트리를 순회하며 문맥 의존 규칙을 적용한 새 트리를 반환한다.

    원본 ``blocks`` 는 변형하지 않고 순수 함수로 동작한다.
    """
    raise NotImplementedError("walk 는 후속 커밋에서 구현된다")
