"""이미지 등록 (계약 3, C 영역).

C 부재 기간 동안 B 가 스텁으로 둔다. 그림 빌더에서 호출되며 스모크
단계(이미지 없는 문서) 에서는 호출되지 않는다.
"""

from __future__ import annotations


__all__ = ["register_image"]


def register_image(src_path: str, work_dir: str) -> tuple[str, dict]:
    """이미지를 work_dir/BinData/ 로 복사하고 (binary_item_id, manifest_entry) 반환.

    스텁 단계에서는 항상 NotImplementedError 를 발생시킨다.
    그림 요소를 포함하는 문서는 이 스텁을 채울 때까지 변환할 수 없다.
    """
    raise NotImplementedError(
        "register_image 의 실제 동작은 이미지 파이프라인 구현 시점에 채워진다"
    )
