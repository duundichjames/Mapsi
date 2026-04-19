"""스타일 매핑 YAML 로더 (계약 1, C 영역).

C 부재 기간 동안 B 가 임시 구현. ``spec/styles.yaml`` 을 dict 로 로드하며,
heading / bullet_list / ordered_list 의 깊이 키를 정수로 정규화한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


__all__ = ["load_style_map"]


_NESTED_ROLES = ("heading", "bullet_list", "ordered_list")


def load_style_map(yaml_path: str | Path) -> dict[str, Any]:
    """spec/styles.yaml 을 로드해 스타일 매핑 딕셔너리를 반환한다."""
    raw = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"styles.yaml 의 최상위가 매핑이 아님: {yaml_path}")

    for role in _NESTED_ROLES:
        if role in raw and isinstance(raw[role], dict):
            raw[role] = {int(k): v for k, v in raw[role].items()}
    return raw
