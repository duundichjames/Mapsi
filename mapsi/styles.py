"""역할 키워드 → 한/글 HWPX 스타일 이름 조회.

본 모듈은 ``spec/styles.yaml`` 에서 로드된 매핑 딕셔너리를 받아 역할
문자열과 깊이로부터 한/글 스타일 *이름* 을 반환하는 순수 함수를 제공한다.
빌더 코드는 이 이름을 키로 ``builder.header.parse_style_table()`` 결과를
조회해 실제 ``id`` / ``paraPrIDRef`` / ``charPrIDRef`` 정수값을 얻는다.

설계 노트
---------
이전 구현은 yaml 에 ``id`` 정수까지 박아놓고 ``style_id()`` 로 조회했다.
하지만 ID 의 진실원은 ``templates/Contents/header.xml`` 한 곳이어야 하므로
yaml 에서 정수 ID 를 빼고 이름만 남겼다. 이름 → 엔트리 룩업은 빌더가
``style_table[name]`` 으로 직접 수행한다.
"""

from __future__ import annotations

from typing import Any


__all__ = ["StyleLookupError", "style_name"]


class StyleLookupError(KeyError):
    """역할/깊이 조합에 매칭되는 스타일이 없을 때 발생한다."""


# 깊이 키를 갖는 역할 (heading / bullet_list / ordered_list)
_NESTED_ROLES = frozenset({"heading", "bullet_list", "ordered_list"})


def style_name(style_map: dict[str, Any], role: str, depth: int = 1) -> str:
    """역할 키워드와 깊이로 한/글 스타일 이름을 조회한다.

    Args:
        style_map: ``config.load_style_map()`` 의 반환 딕셔너리.
        role: ``spec/styles.yaml`` 의 최상위 키와 동일한 역할 문자열.
        depth: heading / bullet_list / ordered_list 처럼 깊이 키를 갖는
            역할에서만 의미 있다. 그 외에는 무시된다.

    Returns:
        한/글 ``header.xml`` 의 ``hh:style/@name`` 과 1:1 대응되는 이름.

    Raises:
        StyleLookupError: 역할 또는 깊이가 매핑에 없을 때.
    """
    if role not in style_map:
        raise StyleLookupError(f"알 수 없는 역할: {role!r}")
    entry = style_map[role]
    if role in _NESTED_ROLES:
        if not isinstance(entry, dict) or depth not in entry:
            available = sorted(k for k in (entry or {}) if isinstance(k, int))
            raise StyleLookupError(
                f"역할 {role!r} 의 깊이 {depth} 가 정의되지 않음 "
                f"(가능: {available})"
            )
        return str(entry[depth])
    return str(entry)
