"""pytest 공용 픽스처.

세션 시작 시 ``MAPSI_NO_LLM=1`` 을 강제 설정해 수식 변환이 항상 폴백
경로를 타도록 한다. 이는 골든 회귀의 결정론을 보장하기 위함이며 (ADR
0002), 사용자 환경에 ``ANTHROPIC_API_KEY`` 등이 있어도 테스트 결과는
영향받지 않는다. 또한 수식 캐시 경로를 임시 디렉토리로 격리해 로컬
``~/.mapsi/equation_cache.json`` 을 오염시키지 않는다.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


# 세션 시작 시 즉시 적용 (collect 단계에서 import 되는 모듈도 보호).
os.environ["MAPSI_NO_LLM"] = "1"
_CACHE_TMP = Path(tempfile.mkdtemp(prefix="mapsi-test-cache-")) / "equation_cache.json"
os.environ["MAPSI_EQUATION_CACHE"] = str(_CACHE_TMP)


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """리포지토리 루트 경로를 반환한다."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def samples_dir(repo_root: Path) -> Path:
    """`samples/` 디렉토리 경로."""
    return repo_root / "samples"


@pytest.fixture(scope="session")
def templates_dir(repo_root: Path) -> Path:
    """`templates/` 디렉토리 경로."""
    return repo_root / "templates"


@pytest.fixture(scope="session")
def spec_dir(repo_root: Path) -> Path:
    """`spec/` 디렉토리 경로."""
    return repo_root / "spec"
