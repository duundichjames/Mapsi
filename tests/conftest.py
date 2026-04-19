"""pytest 공용 픽스처."""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


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
