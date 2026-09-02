"""Runtime settings for the Phase 1 simulator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Application settings derived from the project root."""

    project_root: Path
    data_dir: Path
    database_path: Path
    sample_csv_path: Path
    tick_minutes: int = 1
    historical_tick_minutes: int = 5
    live_tick_seconds: float = 1.0
    default_seed: int = 42


def get_settings(project_root: Path | None = None) -> Settings:
    """Return paths and defaults for the local project."""

    root = project_root or Path(__file__).resolve().parent.parent
    data_dir = root / "data"
    return Settings(
        project_root=root,
        data_dir=data_dir,
        database_path=data_dir / "aquasense_phase1_v1.db",
        sample_csv_path=data_dir / "telemetry_sample.csv",
    )
