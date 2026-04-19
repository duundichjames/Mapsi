"""header.xml 로더.

``templates/Contents/header.xml`` 은 모든 스타일 정의가 누적된 마스터 헤더이며,
변환기는 이 파일을 동적으로 조립하지 않는다. 본 모듈은 단순 로드만 담당한다
(개발자 핸드오프 §3.1 의 "header.xml 의 불변성").
"""

from __future__ import annotations

from pathlib import Path


__all__ = ["load_header"]


def load_header(template_path: str | Path) -> bytes:
    """header.xml 을 바이트로 읽어 그대로 반환한다.

    인코딩 변환이나 정규화를 수행하지 않는다 (lxml 의 C14N 비교 시
    원본 바이트 보존이 유리하기 때문).
    """
    return Path(template_path).read_bytes()
