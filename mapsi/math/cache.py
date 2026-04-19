"""LaTeX → HNC 수식 변환 결과의 로컬 JSON 캐시 (계약 7 보조, C 영역).

C 부재 기간 동안 B 가 스텁으로 둔다. ``~/.mapsi/equation_cache.json`` 에
(sha256(latex)[:16] → 변환결과) 쌍을 저장한다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


__all__ = ["cache_path", "cache_key", "load", "save"]


def cache_path() -> Path:
    return Path.home() / ".mapsi" / "equation_cache.json"


def cache_key(latex: str) -> str:
    return hashlib.sha256(latex.encode("utf-8")).hexdigest()[:16]


def load() -> dict[str, str]:
    path = cache_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save(cache: dict[str, str]) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
