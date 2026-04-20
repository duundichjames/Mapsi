"""스타일 매핑 YAML 로더 (계약 1, C 영역)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


__all__ = ["load_style_map"]


_NESTED_ROLES = ("heading", "bullet_list", "ordered_list")
_SIMPLE_STYLE_ROLES = {
    "paragraph",
    "blockquote",
    "code_block",
    "table_cell",
    "table_caption",
    "figure",
    "figure_caption",
    "footnote",
    "reference",
    "memo",
}
_METADATA_KEYS = {
    "version",
    "header_template",
}


def load_style_map(yaml_path: str | Path) -> dict[str, Any]:
    """spec/styles.yaml 을 로드해 스타일 매핑 딕셔너리를 반환한다."""
    path = Path(yaml_path)

    if not path.is_file():
        raise FileNotFoundError(f"styles.yaml 파일을 찾을 수 없음: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"styles.yaml 파싱 실패 ({path}): {exc}") from exc

    if raw is None:
        raw = {}

    if not isinstance(raw, dict):
        raise ValueError(
            "styles.yaml 의 최상위는 매핑(dict) 이어야 함: "
            f"type={type(raw).__name__}, path={path}"
        )

    normalized: dict[str, Any] = {}

    for role, value in raw.items():
        if role in _NESTED_ROLES:
            normalized[role] = _normalize_nested_role(role, value, path)
        elif role in _SIMPLE_STYLE_ROLES:
            normalized[role] = _normalize_simple_role(role, value, path)
        elif role in _METADATA_KEYS:
            normalized[role] = value
        else:
            # 알 수 없는 추가 키는 그대로 보존한다.
            normalized[role] = value

    paragraph = normalized.get("paragraph")
    if not isinstance(paragraph, str) or not paragraph.strip():
        raise ValueError(
            f"styles.yaml 에 'paragraph' 역할이 없거나 비어 있음: {path}"
        )

    return normalized


def _normalize_nested_role(role: str, value: Any, path: Path) -> dict[int, str]:
    if not isinstance(value, dict):
        raise ValueError(
            f"styles.yaml 의 {role!r} 값은 깊이별 매핑(dict) 이어야 함: "
            f"type={type(value).__name__}, path={path}"
        )

    normalized: dict[int, str] = {}
    for depth_key, style_name in value.items():
        try:
            depth = int(depth_key)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"styles.yaml 의 {role!r} 하위 키는 정수여야 함: "
                f"invalid_key={depth_key!r}, path={path}"
            ) from exc

        if not isinstance(style_name, str) or not style_name.strip():
            raise ValueError(
                f"styles.yaml 의 {role!r}[{depth_key!r}] 값은 비어 있지 않은 문자열이어야 함: "
                f"path={path}"
            )

        normalized[depth] = style_name

    return normalized


def _normalize_simple_role(role: str, value: Any, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"styles.yaml 의 {role!r} 값은 비어 있지 않은 문자열이어야 함: "
            f"type={type(value).__name__}, path={path}"
        )
    return value

