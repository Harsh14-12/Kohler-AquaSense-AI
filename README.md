# KOHLER AquaSense AI

## Autonomous AI Operating Layer for Commercial Smart Facilities

**KOHLER-MITWPU AI Research Lab Program — Track 2: Commercial Smart Facility & Sustainability Manager**

KOHLER AquaSense AI is a research prototype for an intelligent commercial-facility operations layer that transforms synthetic IoT telemetry into explainable anomaly detection, sustainability impact estimates, maintenance risk scores, and actionable maintenance tickets.

The system is designed around a simple operational loop:

**Sense → Understand → Explain → Quantify → Prioritize → Act**

---

## 1. Problem Statement

Commercial facilities such as airports, hospitals, and universities operate large numbers of water fixtures and restroom systems.

Operational teams need to answer questions such as:

- Is a fixture behaving abnormally?
- Is water being wasted?
- Why was the fixture flagged?
- How serious is the issue?
- What is the estimated sustainability impact?
- Which issue should maintenance address first?
- Has a maintenance ticket already been created?

Traditional monitoring can expose raw telemetry without turning it into an operational decision.

**AquaSense AI converts telemetry into explainable operational intelligence.**

---

## 2. Proposed Solution

AquaSense processes facility telemetry through an end-to-end decision pipeline:

```text
Synthetic IoT Telemetry
        ↓
Feature Engineering
        ↓
Deterministic Rule Detection
        ↓
ML Anomaly Detection
        ↓
Rule + ML Fusion
        ↓
Explainable Anomaly Event
        ↓
Sustainability Impact
        ↓
Maintenance Risk Score
        ↓
Maintenance Ticket
        ↓
Streamlit Operations Dashboard