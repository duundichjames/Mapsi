"""역할 키워드 → 한/글 HWPX 스타일 ID 매핑.

본 모듈은 ``spec/styles.yaml`` 에서 로드된 매핑 딕셔너리를 받아 역할
문자열과 깊이로부터 정수 ID 를 반환하는 순수 함수를 제공한다. 빌더 코드
어디에서도 ID 숫자를 직접 사용하지 않으며, 항상 본 모듈을 경유한다.
"""

from __future__ import annotations

from typing import Any


__all__ = ["StyleLookupError", "style_id", "style_name"]


class StyleLookupError(KeyError):
    """역할/깊이 조합에 매칭되는 스타일이 없을 때 발생한다."""


# 깊이 키를 갖는 역할 (heading / bullet_list / ordered_list)
_NESTED_ROLES = frozenset({"heading", "bullet_list", "ordered_list"})


def _resolve(style_map: dict[str, Any], role: str, depth: int) -> dict[str, Any]:
    if role not in style_map:
        raise StyleLookupError(f"알 수 없는 역할: {role!r}")
    entry = style_map[role]
    if role in _NESTED_ROLES:
        if depth not in entry:
            available = sorted(k for k in entry if isinstance(k, int))
            raise StyleLookupError(
                f"역할 {role!r} 의 깊이 {depth} 가 정의되지 않음 "
                f"(가능: {available})"
            )
        return entry[depth]
    return entry


def style_id(style_map: dict[str, Any], role: str, depth: int = 1) -> int:
    """역할 키워드와 깊이로 스타일 ID 를 조회한다.

    Args:
        style_map: ``config.load_style_map()`` 의 반환 딕셔너리.
        role: ``spec/styles.yaml`` 의 최상위 키와 동일한 역할 문자열.
        depth: heading / bullet_list / ordered_list 처럼 깊이 키를 갖는
            역할에서만 의미 있다. 그 외에는 무시된다.

    Returns:
        ``hh:style/@id`` 와 ``hp:p/@styleIDRef`` 가 참조하는 정수 ID.

    Raises:
        StyleLookupError: 역할 또는 깊이가 매핑에 없을 때.
    """
    return int(_resolve(style_map, role, depth)["id"])


def style_name(style_map: dict[str, Any], role: str, depth: int = 1) -> str:
    """역할 키워드와 깊이로 사용자 노출 스타일 이름을 조회한다."""
    return str(_resolve(style_map, role, depth)["name"])
