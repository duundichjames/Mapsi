"""content.hpf manifest 갱신 (계약 4, C 영역).

C 부재 기간 동안 B 가 스텁으로 둔다. 이미지/멀티미디어 등록 시점에 호출되며
스모크 단계에서는 호출되지 않는다.
"""

from __future__ import annotations


__all__ = ["update_manifest"]


def update_manifest(content_hpf_path: str, entries: list[dict]) -> None:
    """content.hpf 의 opf:manifest 를 in-place 로 갱신한다.

    스텁 동작:
        ``entries`` 가 비어 있으면 no-op 으로 통과한다 (이미지 없는
        문서 변환의 일반 경로). 비어 있지 않으면 ``NotImplementedError``.
    """
    if not entries:
        return
    raise NotImplementedError(
        "update_manifest 의 실제 동작은 이미지 파이프라인과 함께 구현된다"
    )
