from __future__ import annotations

from pathlib import Path

import pytest

from reconciliation.config import load_config
from reconciliation.models import MappingConfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config() -> MappingConfig:
    return load_config(ROOT / "examples" / "mapping.json")


@pytest.fixture
def example_paths() -> tuple[Path, Path]:
    return ROOT / "examples" / "source_a.csv", ROOT / "examples" / "source_b.csv"
