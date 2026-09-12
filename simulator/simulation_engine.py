"""Tick-based simulation engine with live and historical modes."""

from __future__ import annotations

import argparse
import csv
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config.settings import get_settings
from database.db import create_session_factory, init_db
from database.repository import TelemetryRepository
from app.pipeline import AquaSensePipeline
from schemas.telemetry import SensorReading
from simulator.facility_topology import (
    FacilityTopology,
    ZoneDefinition,
    available_presets,
    build_facility_topology,
)

from .fault_injector import FaultInjector
from .occupancy_model import OccupancyModel
from .sensor_emulator import SensorEmulator


@dataclass
class TickResult:
    timestamp: datetime
    readings: list[SensorReading]
    occupancy_by_zone: dict[str, int]


@dataclass
class HistoricalGenerationSummary:
    total_readings: int
    sample_readings: list[SensorReading]
    database_path: Path
    sample_csv_path: Path


class SimulationEngine:
    """Coordinate topology, occupancy, faults, telemetry, and persistence."""

    def __init__(
        self,
        preset_name: str,
        database_path: Path | None = None,
        start_time: datetime | None = None,
        tick_minutes: int = 1,
        live_tick_seconds: float = 1.0,
        seed: int = 42,
    ) -> None:
        if tick_minutes <= 0:
            raise ValueError("tick_minutes must be positive")

        settings = get_settings()

        self.database_path = database_path or settings.database_path
        self.topology: FacilityTopology = build_facility_topology(
            preset_name
        )
        self.tick_minutes = tick_minutes
        self.live_tick_seconds = live_tick_seconds

        self.current_time = (
            start_time
            or datetime(
                2026,
                1,
                5,
                6,
                0,
                tzinfo=timezone.utc,
            )
        )

        self._rng = random.Random(seed)

        self.occupancy_model = OccupancyModel()
        self.sensor_emulator = SensorEmulator()
        self.fault_injector = FaultInjector()

        init_db(self.database_path)

        self.repository = TelemetryRepository(
            create_session_factory(self.database_path)
        )

        self.repository.register_topology(self.topology)

        # End-to-end AquaSense AI processing
        self.pipeline = AquaSensePipeline()

        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def inject_fault(
        self,
        fault_type: str,
        duration_minutes: int,
        severity: str,
        **targets: str,
    ) -> None:
        """Add a fault starting at the engine's current simulated time."""

        self.fault_injector.inject_fault(
            fault_type=fault_type,
            duration_minutes=duration_minutes,
            severity=severity,
            start_time=self.current_time,
            fixture_id=targets.get("fixture_id"),
            sensor_id=targets.get("sensor_id"),
            zone_id=targets.get("zone_id"),
        )

    def run_tick(self, persist: bool = True) -> TickResult:
        """Generate telemetry for a single simulation tick."""

        active_faults = self.fault_injector.get_active_faults(
            self.current_time
        )

        occupancy_by_zone = {
            zone.zone_id: self._zone_occupancy(
                zone,
                active_faults,
            )
            for zone in self.topology.zones
        }

        readings = self.sensor_emulator.generate_tick_readings(
            timestamp=self.current_time,
            topology=self.topology,
            occupancy_by_zone=occupancy_by_zone,
            active_faults=active_faults,
            rng=self._rng,
        )

        if persist:
            # 1. Persist raw telemetry
            self.repository.save_sensor_readings(readings)

            # 2. Process telemetry through AquaSense AI
            for reading in readings:
                pipeline_result = self.pipeline.process_reading(
                    reading
                )

                # 3. Persist maintenance ticket, including
                # sustainability impact evidence.
                if pipeline_result.maintenance_ticket is not None:
                    self.repository.save_maintenance_ticket(
                        pipeline_result.maintenance_ticket
                    )

        result = TickResult(
            timestamp=self.current_time,
            readings=readings,
            occupancy_by_zone=occupancy_by_zone,
        )

        self.current_time += timedelta(
            minutes=self.tick_minutes
        )

        return result

    def run_live(
        self,
        ticks: int | None = None,
    ) -> list[TickResult]:
        """Run the simulator in live mode."""

        self.start()

        results: list[TickResult] = []
        iterations = 0

        while self._running:
            results.append(self.run_tick())

            iterations += 1

            if ticks is not None and iterations >= ticks:
                self.stop()
                break

            time.sleep(self.live_tick_seconds)

        return results

    def run_historical(
        self,
        duration: timedelta,
        persist: bool = True,
    ) -> list[TickResult]:
        """Generate historical telemetry quickly without real-time sleeps."""

        total_minutes = int(
            duration.total_seconds() // 60
        )

        steps = total_minutes // self.tick_minutes

        return [
            self.run_tick(persist=persist)
            for _ in range(steps)
        ]

    def _zone_occupancy(
        self,
        zone: ZoneDefinition,
        active_faults,
    ) -> int:
        occupancy = self.occupancy_model.get_expected_occupancy(
            timestamp=self.current_time,
            facility_type=self.topology.facility.facility_type,
            zone_type=zone.zone_type,
            zone_capacity=zone.capacity,
            rng=self._rng,
        )

        for fault in active_faults:
            if (
                fault.fault_type == "occupancy_spike"
                and fault.applies_to_zone(zone.zone_id)
            ):
                occupancy += max(
                    1,
                    int(
                        round(
                            zone.capacity
                            * 0.2
                            * fault.severity_factor
                        )
                    ),
                )

        return max(0, occupancy)


def generate_default_historical_data(
    database_path: Path | None = None,
    sample_csv_path: Path | None = None,
    days: int = 7,
    seed: int = 42,
) -> HistoricalGenerationSummary:
    """Generate a seven-day historical dataset across all facility presets."""

    settings = get_settings()

    db_path = (
        database_path
        or settings.database_path
    )

    csv_path = (
        sample_csv_path
        or settings.sample_csv_path
    )

    total_readings = 0
    sample_readings: list[SensorReading] = []
    batch: list[SensorReading] = []

    batch_row_target = 12_000

    for preset_index, preset_name in enumerate(
        available_presets()
    ):
        start_time = datetime(
            2026,
            1 + preset_index,
            1,
            0,
            0,
            tzinfo=timezone.utc,
        )

        engine = SimulationEngine(
            preset_name=preset_name,
            database_path=db_path,
            start_time=start_time,
            tick_minutes=settings.historical_tick_minutes,
            live_tick_seconds=settings.live_tick_seconds,
            seed=seed + preset_index,
        )

        _schedule_default_faults(engine)

        total_minutes = days * 24 * 60
        steps = total_minutes // engine.tick_minutes

        for _ in range(steps):
            result = engine.run_tick(
                persist=False
            )

            total_readings += len(
                result.readings
            )

            if len(sample_readings) < 500:
                remaining = (
                    500
                    - len(sample_readings)
                )

                sample_readings.extend(
                    result.readings[:remaining]
                )

            batch.extend(result.readings)

            if len(batch) >= batch_row_target:
                engine.repository.save_sensor_readings(
                    batch
                )
                batch.clear()

        if batch:
            engine.repository.save_sensor_readings(
                batch
            )
            batch.clear()

    _export_sample_csv(
        csv_path,
        sample_readings,
    )

    return HistoricalGenerationSummary(
        total_readings=total_readings,
        sample_readings=sample_readings,
        database_path=db_path,
        sample_csv_path=csv_path,
    )


def _schedule_default_faults(
    engine: SimulationEngine,
) -> None:
    """Schedule a few sparse anomalies into the historical run."""

    zone = engine.topology.zones[0]

    flow_fixture = engine.topology.fixtures[0]

    flush_fixture = next(
        item
        for item in engine.topology.fixtures
        if item.fixture_type
        in {"flush_valve", "urinal"}
    )

    dropout_sensor = engine.topology.sensors[0]

    engine.fault_injector.inject_fault(
        fault_type="continuous_leak",
        fixture_id=flow_fixture.fixture_id,
        duration_minutes=180,
        severity="medium",
        start_time=(
            engine.current_time
            + timedelta(days=1, hours=2)
        ),
    )

    engine.fault_injector.inject_fault(
        fault_type="ghost_flush",
        fixture_id=flush_fixture.fixture_id,
        duration_minutes=90,
        severity="high",
        start_time=(
            engine.current_time
            + timedelta(days=3, hours=1)
        ),
    )

    engine.fault_injector.inject_fault(
        fault_type="sensor_dropout",
        sensor_id=dropout_sensor.sensor_id,
        duration_minutes=120,
        severity="high",
        start_time=(
            engine.current_time
            + timedelta(days=4, hours=5)
        ),
    )

    engine.fault_injector.inject_fault(
        fault_type="abnormal_flow",
        fixture_id=flow_fixture.fixture_id,
        duration_minutes=75,
        severity="medium",
        start_time=(
            engine.current_time
            + timedelta(days=5, hours=3)
        ),
    )

    engine.fault_injector.inject_fault(
        fault_type="occupancy_spike",
        zone_id=zone.zone_id,
        duration_minutes=60,
        severity="medium",
        start_time=(
            engine.current_time
            + timedelta(days=2, hours=8)
        ),
    )


def _export_sample_csv(
    path: Path,
    readings: list[SensorReading],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sensor_id",
                "fixture_id",
                "zone_id",
                "facility_id",
                "timestamp",
                "sensor_type",
                "value",
                "unit",
                "diagnostic_status",
                "quality_flag",
                "metadata",
            ],
        )

        writer.writeheader()

        for reading in readings:
            writer.writerow(
                {
                    "sensor_id": reading.sensor_id,
                    "fixture_id": reading.fixture_id,
                    "zone_id": reading.zone_id,
                    "facility_id": reading.facility_id,
                    "timestamp": reading.timestamp.isoformat(),
                    "sensor_type": reading.sensor_type,
                    "value": reading.value,
                    "unit": reading.unit,
                    "diagnostic_status": reading.diagnostic_status,
                    "quality_flag": reading.quality_flag,
                    "metadata": reading.metadata,
                }
            )


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AquaSense AI Phase 1 simulator"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    historical = subparsers.add_parser(
        "historical",
        help="Generate historical telemetry",
    )

    historical.add_argument(
        "--days",
        type=int,
        default=7,
    )

    historical.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    live = subparsers.add_parser(
        "live",
        help="Run live telemetry simulation",
    )

    live.add_argument(
        "--facility",
        choices=available_presets(),
        default="airport",
    )

    live.add_argument(
        "--ticks",
        type=int,
        default=5,
    )

    live.add_argument(
        "--seed",
        type=int,
        default=42,
    )

    return parser


def main() -> None:
    parser = _build_cli_parser()
    args = parser.parse_args()

    settings = get_settings()

    if args.command == "historical":
        summary = generate_default_historical_data(
            database_path=settings.database_path,
            sample_csv_path=settings.sample_csv_path,
            days=args.days,
            seed=args.seed,
        )

        print(
            f"Generated {summary.total_readings} readings "
            f"into {summary.database_path} "
            f"and {summary.sample_csv_path}"
        )

        return

    engine = SimulationEngine(
        preset_name=args.facility,
        database_path=settings.database_path,
        start_time=datetime(
            2026,
            1,
            5,
            6,
            0,
            tzinfo=timezone.utc,
        ),
        tick_minutes=settings.tick_minutes,
        live_tick_seconds=settings.live_tick_seconds,
        seed=args.seed,
    )

    results = engine.run_live(
        ticks=args.ticks
    )

    for result in results:
        print(
            f"{result.timestamp.isoformat()} "
            f"occupancy="
            f"{sum(result.occupancy_by_zone.values())} "
            f"readings={len(result.readings)}"
        )


if __name__ == "__main__":
    main()