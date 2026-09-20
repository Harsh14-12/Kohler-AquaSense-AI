# KOHLER AquaSense AI

> An Explainable AI-Powered Smart Water Fixture Monitoring, Anomaly Detection, Sustainability Analytics, Predictive Maintenance, and AI Copilot Platform.

---

## 📌 Overview

**KOHLER AquaSense AI** is an end-to-end intelligent water-fixture monitoring platform designed to simulate, analyze, and respond to abnormal fixture behavior in facilities such as airports, commercial buildings, and public infrastructure.

The system combines:

- IoT telemetry simulation
- Feature engineering
- Rule-based anomaly detection
- ML-based anomaly detection
- Decision fusion
- Sustainability impact analysis
- Predictive maintenance risk scoring
- Automated maintenance ticket generation
- AI-powered Copilot assistance
- Persistent telemetry and maintenance data
- Interactive Streamlit dashboard

The platform is designed as an explainable decision-support system rather than an opaque black-box solution.

---

# 🎯 Problem Statement

Modern facilities contain large numbers of water fixtures such as:

- Faucets
- Toilets
- Urinals
- Water lines
- Other connected plumbing assets

Continuous monitoring of these assets can be challenging.

Potential problems include:

- Continuous water leakage
- Abnormal water flow
- Ghost flushing
- Sensor dropout
- Unexpected occupancy behavior
- Repeated fixture anomalies
- Increasing maintenance risk
- Water wastage

AquaSense AI addresses these challenges through a simulated smart-facility pipeline that transforms telemetry into actionable maintenance and sustainability insights.

---

# 💡 Solution

AquaSense AI follows an end-to-end processing pipeline:

```text
IoT Telemetry
      ↓
Feature Engineering
      ↓
Rule + ML Detection
      ↓
Decision Fusion
      ↓
Sustainability Impact
      ↓
Maintenance Risk
      ↓
Automatic Maintenance Ticket
      ↓
AI Copilot



Key Features
1. IoT Telemetry Simulation

The simulator generates realistic facility telemetry including:

Sensor readings
Fixture IDs
Zone information
Facility information
Occupancy
Flow measurements
Diagnostic status
Quality indicators
Timestamped readings

The simulator supports configurable facility presets.



2. Fault Injection

The simulator supports controlled fault injection for testing the complete AI pipeline.

Supported fault types include:

continuous_leak
ghost_flush
sensor_dropout
occupancy_spike
abnormal_flow


Fault severity levels include:

low
medium
high



Faults can be targeted at:

Fixtures
Sensors
Zones

This allows controlled testing of anomaly detection and downstream decision-making.




AI / ML Pipeline
Feature Engineering

Raw telemetry is transformed into interpretable features that can be consumed by the detection and decision layers.

The feature pipeline helps identify patterns such as:

Abnormal flow
Repeated anomalies
Persistent abnormal behavior
Sensor health issues
Fixture-level deviations
🔎 Anomaly Detection

AquaSense combines rule-based and ML-based detection.

Rule-Based Detection

Transparent rules identify known operational patterns such as:

Continuous leaks
Abnormal flow
Ghost flushes
Sensor issues
Machine Learning Detection

The project also contains an ML anomaly detection component for identifying unusual telemetry behavior.

This hybrid architecture combines:

Known operational rules
        +
Data-driven anomaly detection
        ↓
Decision Fusion
🔀 Decision Fusion

Individual detection signals are combined through a decision-fusion layer.

This reduces dependence on a single detector and creates a consolidated anomaly decision.

The resulting decision can contain:

Detection evidence
Anomaly classification
Confidence
Supporting telemetry
Downstream maintenance implications
💧 Sustainability Impact

Detected water-related anomalies are translated into sustainability metrics.

The system can estimate:

Water wasted
Duration of abnormal behavior
Sustainability impact associated with detected faults

For example:

Abnormal flow
      ↓
Leak duration
      ↓
Estimated water loss
      ↓
Sustainability impact

This connects technical fault detection with measurable environmental impact.

🛠️ Predictive Maintenance

AquaSense calculates a transparent maintenance-risk score from multiple factors.

The risk model considers:

Factor	Maximum Contribution
Anomaly Frequency	20
Recent Recurrence	20
Severity	15
Sensor Health	10
Abnormal Flow	10
Persistence	15
Maintenance Age	10
Total	100

Risk categories:

0–29     LOW
30–59    MEDIUM
60–79    HIGH
80–100   CRITICAL

The system also generates an explanation showing the primary contributing factors.

The risk weights are engineering assumptions for this prototype and are not KOHLER operational specifications.

🎫 Automatic Maintenance Tickets

When an actionable anomaly is detected, AquaSense can generate a maintenance ticket containing information such as:

Ticket ID
Fixture
Zone
Anomaly type
Priority
Risk score
Status
Creation timestamp
Title
Supporting evidence

This creates a transition from:

Detection
   ↓
Risk Assessment
   ↓
Maintenance Decision
   ↓
Actionable Ticket
🤖 AquaSense AI Copilot

The project includes an AI Copilot layer designed to answer operational questions using structured AquaSense evidence.

The Copilot architecture contains:

copilot/
├── context.py
├── engine.py
├── llm.py
├── schemas.py
└── tools.py

The Copilot can use evidence from sources such as:

Recent telemetry
Maintenance tickets
Fixture information
Operational context
Deterministic Fallback

The system is designed to remain functional even without an external LLM/API key.

If an LLM is unavailable or fails, the Copilot uses deterministic responses based on the available AquaSense evidence.

This makes the project demonstrable without requiring a paid API.

🗄️ Data Persistence

AquaSense uses SQLite for local persistence.

The database stores information related to:

Telemetry
Facility topology
Fixtures
Sensors
Maintenance tickets

Generated database files are intentionally excluded from GitHub through .gitignore.

The database can therefore be generated locally when running the project.

📊 Interactive Dashboard

The project includes a Streamlit dashboard for visualizing the AquaSense platform.

The dashboard provides views for:

Facility status
Recent telemetry
Telemetry summaries
Maintenance tickets
Ticket history
AI decision pipeline
Sustainability information
Predictive maintenance information
AquaSense Copilot

Run the dashboard with:

.\.venv\Scripts\python.exe -m streamlit run dashboard\app.py

Then open:

http://localhost:8501
🏗️ Project Architecture
KOHLER AquaSense AI
│
├── app/
│   └── pipeline.py
│
├── config/
│   └── settings.py
│
├── copilot/
│   ├── context.py
│   ├── engine.py
│   ├── llm.py
│   ├── schemas.py
│   └── tools.py
│
├── dashboard/
│   └── app.py
│
├── database/
│   ├── db.py
│   ├── models.py
│   └── repository.py
│
├── detection/
│   ├── explainer.py
│   ├── rule_engine.py
│   └── schemas.py
│
├── features/
│   ├── feature_engine.py
│   └── schemas.py
│
├── fusion/
│   ├── fusion_engine.py
│   └── schemas.py
│
├── maintenance/
│   ├── risk_builder.py
│   ├── risk_engine.py
│   ├── schemas.py
│   ├── ticket_engine.py
│   └── ticket_schemas.py
│
├── ml/
│   ├── anomaly_detector.py
│   └── schemas.py
│
├── schemas/
│   └── telemetry.py
│
├── simulator/
│   ├── facility_topology.py
│   ├── fault_injector.py
│   ├── occupancy_model.py
│   ├── sensor_emulator.py
│   └── simulation_engine.py
│
├── sustainability/
│   ├── impact_engine.py
│   └── schemas.py
│
└── tests/
    ├── test_copilot_context.py
    ├── test_copilot_engine.py
    ├── test_copilot_llm.py
    ├── test_copilot_tools.py
    ├── test_database.py
    ├── test_detection.py
    ├── test_features.py
    ├── test_fusion.py
    ├── test_maintenance.py
    ├── test_ml_detector.py
    ├── test_pipeline.py
    ├── test_simulator_pipeline.py
    ├── test_sustainability.py
    └── ...
🧰 Technology Stack
Programming
Python 3
SQL
PowerShell / CLI
Data & Backend
SQLite
SQLAlchemy
Pandas
AI / ML
Rule-based anomaly detection
Machine-learning anomaly detection
Explainable risk scoring
AI Copilot architecture
Deterministic LLM fallback
Dashboard
Streamlit
Testing
Pytest
Development
Git
GitHub
⚙️ Installation

Clone the repository:

git clone https://github.com/Harsh14-12/Kohler-AquaSense-AI.git

Move into the project:

cd Kohler-AquaSense-AI

Create a virtual environment:

python -m venv .venv

Activate it:

.\.venv\Scripts\Activate.ps1

Install dependencies:

pip install -r requirements.txt
▶️ Running the Simulator
Live Simulation

Example:

.\.venv\Scripts\python.exe -m simulator.simulation_engine live --facility airport --ticks 10 --seed 42

Example output:

2026-01-05T06:00:00+00:00 occupancy=83 readings=78
2026-01-05T06:01:00+00:00 occupancy=84 readings=78
2026-01-05T06:02:00+00:00 occupancy=96 readings=78
...
🧪 Running Tests

Run the complete test suite:

.\.venv\Scripts\python.exe -m pytest -q

Current project validation:

140 passed

The tests cover major components including:

Telemetry schemas
Database
Simulator
Occupancy
Fault injection
Feature engineering
Anomaly detection
Decision fusion
Sustainability
Maintenance risk
Ticket generation
Persistence
AI Copilot
🔬 End-to-End Fault Demonstration

A continuous-leak fault can be injected into a simulated fixture.

The resulting flow is:

Injected Continuous Leak
          ↓
Sensor Telemetry
          ↓
Feature Engineering
          ↓
Anomaly Detection
          ↓
Decision Fusion
          ↓
Water-Waste Calculation
          ↓
Maintenance Risk
          ↓
Maintenance Ticket

This demonstrates that the simulator and AquaSense AI pipeline operate together rather than as isolated modules.

🔐 API Key / LLM Requirement

The core AquaSense system does not require an OpenAI API key to operate.

The Copilot includes deterministic fallback behavior so that:

The dashboard can run without an API key.
Tests can run without an external LLM.
Core anomaly detection and maintenance functionality remain available offline.

If an external LLM integration is configured in the future, API credentials should be stored in environment variables and never committed to GitHub.

📁 Generated Data

Generated SQLite databases and simulation output are excluded from version control.

Examples:

data/*.db
data/*.sqlite
data/*.sqlite3
data/*.csv

This keeps the GitHub repository lightweight and prevents large generated files from being committed.

⚠️ Limitations

This project is a prototype research/academic implementation.

Important limitations include:

Telemetry is simulated rather than collected from physical KOHLER fixtures.
Maintenance-risk weights are engineering assumptions.
ML anomaly detection performance depends on the available data.
Sustainability calculations are estimates.
The Copilot's deterministic fallback is not equivalent to a full LLM.
The system is intended for decision support and demonstration rather than direct autonomous control of physical plumbing infrastructure.
🔮 Future Scope

Potential future improvements include:

Integration with real IoT sensor streams
MQTT-based telemetry ingestion
Real-time cloud deployment
Advanced time-series anomaly detection
Transformer-based forecasting
Automated model retraining
Digital twin visualization
Multi-facility monitoring
Role-based maintenance workflows
Mobile maintenance notifications
Integration with enterprise CMMS platforms
Real-world water consumption benchmarking
Advanced LLM-based operational analytics
📈 Project Impact

AquaSense AI demonstrates how multiple AI and software-engineering components can be combined into a single intelligent facility-management platform.

The project connects:

Telemetry
   ↓
AI Detection
   ↓
Explainability
   ↓
Sustainability
   ↓
Predictive Maintenance
   ↓
Automated Action
   ↓
AI Assistance

This provides a complete prototype architecture for intelligent water-fixture monitoring.

👨‍💻 Contributors
Harshwardhan Bhatt

MIT World Peace University
B.Tech CSE — Artificial Intelligence & Data Science

📜 Project Status

Status: Prototype / Academic Research Project

Test Status:

140 tests passed

Repository:

https://github.com/Harsh14-12/Kohler-AquaSense-AI





