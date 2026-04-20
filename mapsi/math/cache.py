"""LaTeX → HNC 수식 변환 결과의 로컬 JSON 캐시 (계약 7 보조, C 영역).

기본 위치는 ``~/.mapsi/equation_cache.json`` 이며, 환경 변수
``MAPSI_EQUATION_CACHE`` 가 설정되어 있으면 그 경로를 사용한다 (테스트
격리용).

저장 구조 (JSON 객체)::

    {
        "<sha256(latex|display)[:16]>": "<변환 결과 문자열>",
        ...
    }

키 생성 시 ``display`` 모드를 함께 해시하는 이유는 같은 LaTeX 라도
inline / display 에서 LLM 의 출력이 달라질 수 있기 때문이다 (예: 분수의
공백 처리). 캐시 항목은 *변환 결과 그대로* 저장하며, ``[hnc 수식]`` 마커는
포함하지 않는다 (마커 부착은 :func:`mapsi.math.converter.convert_equation`
의 책임).

손상된 캐시 (JSON 파싱 실패) 는 조용히 빈 dict 로 fallback 한다 — 캐시는
보조 가속 장치일 뿐 정합성의 원천이 아니므로 변환을 막지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


__all__ = ["cache_path", "cache_key", "load", "save", "lookup", "store"]


_DEFAULT_PATH = Path.home() / ".mapsi" / "equation_cache.json"


def cache_path() -> Path:
    """현재 활성 캐시 파일 경로. 환경 변수 우선, 없으면 기본값."""
    override = os.environ.get("MAPSI_EQUATION_CACHE")
    if override:
        return Path(override)
    return _DEFAULT_PATH


def cache_key(latex: str, display: bool) -> str:
    """``(latex, display)`` 의 해시 키 (sha256, 앞 16 자)."""
    payload = f"{latex}|{int(bool(display))}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def load() -> dict[str, str]:
    """캐시 파일을 dict 로 로드. 없거나 손상되면 빈 dict."""
    path = cache_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def save(cache: dict[str, str]) -> None:
    """캐시 dict 을 atomically 저장 (디렉토리 자동 생성)."""
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(path)


def lookup(latex: str, display: bool) -> str | None:
    """``(latex, display)`` 변환 결과를 캐시에서 조회. miss 면 ``None``."""
    return load().get(cache_key(latex, display))


def store(latex: str, display: bool, result: str) -> None:
    """``(latex, display) → result`` 를 캐시에 추가 저장 (멱등 덮어쓰기)."""
    cache = load()
    cache[cache_key(latex, display)] = result
    save(cache)
