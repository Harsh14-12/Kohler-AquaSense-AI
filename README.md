# KOHLER AquaSense AI

KOHLER AquaSense AI is a case-study prototype for the KOHLER-MITWPU AI Research Lab Program. This repository currently implements only the data foundation for a smart commercial water-facility operating layer.

## Current Phase

Phase 1 - Data Model + Realistic IoT Simulator

This phase includes:

- Configurable facility topologies for airport, hospital, and university presets
- A time-aware synthetic occupancy model
- Event-driven flow, flush, occupancy, and diagnostic telemetry generation
- Extensible fault injection
- SQLite persistence for facilities, zones, fixtures, sensors, and sensor readings

The following are intentionally out of scope in this repository today:

- anomaly detection
- predictive maintenance
- sustainability scoring
- FastAPI
- dashboards
- AI copilot or LLM features

## Architecture

Facility topology
    ->
Occupancy model
    ->
Sensor emulator
    ->
Fault injector
    ->
Telemetry schema
    ->
SQLite

## Installation

The implementation is verified against Python 3.10.

Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Historical Data Generation

Generate seven days of telemetry for all three facility presets. The historical generator uses a 5-minute simulation cadence to keep long runs practical while live mode stays at 1 minute per tick:

```powershell
py -3.10 -m simulator.simulation_engine historical --days 7 --seed 42
```

This writes:

- `data/aquasense_phase1_v1.db`
- `data/telemetry_sample.csv`

## Running The Simulator

Run the live simulator for a chosen facility:

```powershell
py -3.10 -m simulator.simulation_engine live --facility airport --ticks 5 --seed 42
```

## Testing

```powershell
py -3.10 -m pytest
```

## Example Telemetry

```text
sensor_id: airport_terminal-terminal-a-restroom-a1-water-line-01-occupancy
fixture_id: airport_terminal-terminal-a-restroom-a1-water-line-01
zone_id: airport_terminal-terminal-a-restroom-a1
facility_id: airport_terminal
timestamp: 2026-01-06T08:00:00+00:00
sensor_type: occupancy_pir
value: 18
unit: persons
diagnostic_status: ok
quality_flag: valid
metadata: {"fixture_type": "water_line", "zone_type": "restroom_airside", "occupancy": 18, "faults": []}
```

## Fault Injection

Programmatic example:

```python
from datetime import datetime, timezone

from simulator.simulation_engine import SimulationEngine

engine = SimulationEngine(
    preset_name="university",
    start_time=datetime(2026, 1, 7, 2, 0, tzinfo=timezone.utc),
    seed=42,
)

fixture_id = engine.topology.fixtures[0].fixture_id
engine.inject_fault(
    fault_type="continuous_leak",
    fixture_id=fixture_id,
    duration_minutes=30,
    severity="high",
)
result = engine.run_tick()
```

Other supported fault types:

- `ghost_flush`
- `sensor_dropout`
- `occupancy_spike`
- `abnormal_flow`

## Prototype Notes

All telemetry in this prototype is synthetically generated for demonstration purposes and does not represent measured KOHLER operational data.

Thresholds, occupancy curves, flow behavior, and fault severities in this prototype are simulation assumptions for evaluation purposes and are not KOHLER operational specifications.

