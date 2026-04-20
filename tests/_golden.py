"""골든 회귀 테스트용 헬퍼 (얇은 어댑터).

핵심 추출 로직은 ``mapsi.inspect`` 로 승격되어 단일 진실원으로 통합됨.
본 모듈은 골든 테스트가 추가로 필요한 :func:`load_expected` 유틸과
하위 호환을 위해 재익스포트한 심볼들만 보관한다.

신규 코드는 ``mapsi.inspect`` 를 직접 import 하길 권장.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mapsi.inspect import (
    HWPML_HEAD_NS,
    HWPML_PARA_NS,
    HWPML_SECTION_NS,
    ParagraphInfo,
    extract_paragraph_sequence,
    extract_style_id_to_name,
    filter_nonempty,
)


__all__ = [
    "HWPML_HEAD_NS",
    "HWPML_PARA_NS",
    "HWPML_SECTION_NS",
    "NS",
    "ParagraphInfo",
    "extract_paragraph_sequence",
    "filter_nonempty",
    "load_expected",
]


NS = {
    "hp": HWPML_PARA_NS,
    "hh": HWPML_HEAD_NS,
    "hs": HWPML_SECTION_NS,
}


def load_expected(fixture_dir: Path) -> dict:
    """``<fixture_dir>/expected.yaml`` 을 로드한다."""
    yaml_path = fixture_dir / "expected.yaml"
    with yaml_path.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


# 하위 호환: 옛 이름의 private 헬퍼를 사용하는 외부 코드가 있을 경우를 위해 유지.
_build_style_id_to_name = extract_style_id_to_name
