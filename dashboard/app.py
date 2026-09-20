from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re

import pandas as pd
import streamlit as st

from database.db import create_session_factory, init_db
from database.repository import TelemetryRepository

from copilot.context import AquaSenseCopilotContext
from copilot.engine import AquaSenseCopilotEngine
from copilot.tools import AquaSenseCopilotTools
from copilot.llm import AquaSenseLLM


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="KOHLER AquaSense AI",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "aquasense.db"
)


# ============================================================
# CUSTOM STYLING
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0;
    }

    .subtitle {
        color: #6b7280;
        font-size: 1.05rem;
        margin-top: 0.2rem;
    }

    .status-card {
        padding: 1.2rem;
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 14px;
        min-height: 130px;
    }

    .status-title {
        font-size: 1.05rem;
        font-weight: 650;
    }

    .status-description {
        color: #6b7280;
        margin-top: 0.5rem;
    }

    .incident-card {
        padding: 1.25rem;
        border: 1px solid rgba(239, 68, 68, 0.35);
        border-radius: 16px;
        background: rgba(239, 68, 68, 0.04);
        margin-bottom: 1rem;
    }

    .incident-title {
        font-size: 1.25rem;
        font-weight: 700;
    }

    .incident-subtitle {
        color: #9ca3af;
        margin-top: 0.25rem;
    }

    .reason-card {
        padding: 1rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        min-height: 150px;
    }

    .reason-title {
        font-weight: 650;
        margin-bottom: 0.5rem;
    }

    .impact-card {
        padding: 1rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        min-height: 120px;
    }

    .impact-value {
        font-size: 1.65rem;
        font-weight: 700;
    }

    .impact-label {
        color: #9ca3af;
        margin-top: 0.2rem;
    }

    .pipeline-step {
        padding: 0.8rem;
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
        text-align: center;
        min-height: 75px;
    }

    .small-muted {
        color: #9ca3af;
        font-size: 0.85rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

try:
    init_db(DATABASE_PATH)

    session_factory = create_session_factory(
        DATABASE_PATH
    )

    repository = TelemetryRepository(
        session_factory
    )

    copilot_tools = AquaSenseCopilotTools(
        repository
    )

    copilot_context = AquaSenseCopilotContext(
        copilot_tools
    )

# ------------------------------------------------------------
# Optional OpenAI LLM
# ------------------------------------------------------------
#
# AquaSense does NOT require an API key.
#
# If OPENAI_API_KEY exists, the LLM can be enabled.
# Otherwise the engine automatically uses its deterministic
# local reasoning layer.
#

    copilot_llm = None

    if os.getenv("OPENAI_API_KEY"):
        try:
            copilot_llm = AquaSenseLLM()
        except Exception:
            copilot_llm = None

    copilot_engine = AquaSenseCopilotEngine(
        copilot_context,
        llm=copilot_llm,
    )

except Exception as exc:
    st.error(
        "Unable to initialize the AquaSense database."
    )
    st.exception(exc)
    st.stop()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_getattr(
    obj,
    name: str,
    default=None,
):
    return getattr(
        obj,
        name,
        default,
    )


def clean_enum(value) -> str:
    """
    Convert enum-style strings such as:
    TicketPriority.HIGH
    into:
    HIGH
    """
    if value is None:
        return ""

    text = str(value)

    if "." in text:
        text = text.split(".")[-1]

    return text.replace("_", " ").upper()


def pretty_anomaly(value) -> str:
    if value is None:
        return ""

    text = str(value)

    if "." in text:
        text = text.split(".")[-1]

    return text.replace("_", " ").title()


def readings_to_dataframe(
    readings,
) -> pd.DataFrame:

    rows = []

    for reading in readings:

        rows.append(
            {
                "Timestamp": safe_getattr(
                    reading,
                    "timestamp",
                ),
                "Facility": safe_getattr(
                    reading,
                    "facility_id",
                ),
                "Zone": safe_getattr(
                    reading,
                    "zone_id",
                ),
                "Fixture": safe_getattr(
                    reading,
                    "fixture_id",
                ),
                "Sensor": safe_getattr(
                    reading,
                    "sensor_id",
                ),
                "Sensor Type": clean_enum(
                    safe_getattr(
                        reading,
                        "sensor_type",
                        "",
                    )
                ),
                "Value": safe_getattr(
                    reading,
                    "value",
                    0,
                ),
                "Unit": clean_enum(
                    safe_getattr(
                        reading,
                        "unit",
                        "",
                    )
                ),
                "Diagnostic": clean_enum(
                    safe_getattr(
                        reading,
                        "diagnostic_status",
                        "",
                    )
                ),
                "Quality": clean_enum(
                    safe_getattr(
                        reading,
                        "quality_flag",
                        "",
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


def tickets_to_dataframe(
    tickets,
) -> pd.DataFrame:

    rows = []

    for ticket in tickets:

        rows.append(
            {
                "Ticket ID": safe_getattr(
                    ticket,
                    "ticket_id",
                ),
                "Facility": safe_getattr(
                    ticket,
                    "facility_id",
                ),
                "Zone": safe_getattr(
                    ticket,
                    "zone_id",
                ),
                "Fixture": safe_getattr(
                    ticket,
                    "fixture_id",
                ),
                "Anomaly": pretty_anomaly(
                    safe_getattr(
                        ticket,
                        "anomaly_type",
                        "",
                    )
                ),
                "Priority": clean_enum(
                    safe_getattr(
                        ticket,
                        "priority",
                        "",
                    )
                ),
                "Risk Score": safe_getattr(
                    ticket,
                    "risk_score",
                    0,
                ),
                "Status": clean_enum(
                    safe_getattr(
                        ticket,
                        "status",
                        "",
                    )
                ),
                "Created": safe_getattr(
                    ticket,
                    "created_at",
                ),
                "Title": safe_getattr(
                    ticket,
                    "title",
                    "",
                ),
                "Description": safe_getattr(
                    ticket,
                    "description",
                    "",
                ),
                "Recommended Action": safe_getattr(
                    ticket,
                    "recommended_action",
                    "",
                ),
                "Evidence": safe_getattr(
                    ticket,
                    "evidence",
                    {},
                ),
            }
        )

    return pd.DataFrame(rows)


def normalize_evidence(evidence):
    """
    Make ticket evidence safe for display.
    """
    if evidence is None:
        return {}

    if isinstance(evidence, dict):
        return evidence

    if isinstance(evidence, str):

        try:
            parsed = json.loads(evidence)

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass

    return {}


def find_numeric_value(
    evidence: dict,
    names: list[str],
):
    """
    Recursively search ticket evidence for a numeric field.
    """
    if not isinstance(evidence, dict):
        return None

    normalized_names = {
        name.lower()
        for name in names
    }

    for key, value in evidence.items():

        key_normalized = str(key).lower()

        if (
            key_normalized in normalized_names
            and isinstance(value, (int, float))
        ):
            return float(value)

        if isinstance(value, dict):

            found = find_numeric_value(
                value,
                names,
            )

            if found is not None:
                return found

    return None


def find_text_value(
    evidence: dict,
    names: list[str],
):
    """
    Recursively search ticket evidence for text.
    """
    if not isinstance(evidence, dict):
        return None

    normalized_names = {
        name.lower()
        for name in names
    }

    for key, value in evidence.items():

        key_normalized = str(key).lower()

        if (
            key_normalized in normalized_names
            and isinstance(value, str)
        ):
            return value

        if isinstance(value, dict):

            found = find_text_value(
                value,
                names,
            )

            if found is not None:
                return found

    return None


def display_fixture_name(
    fixture_id: str,
) -> str:

    if not fixture_id:
        return "Unknown fixture"

    parts = fixture_id.split("-")

    if len(parts) >= 2:
        return parts[-2].replace(
            "_",
            " ",
        ).title() + " " + parts[-1]

    return fixture_id


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">💧 KOHLER AquaSense AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "Commercial Smart Facility & Sustainability Manager"
    "</div>",
    unsafe_allow_html=True,
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("AquaSense Control")

    st.caption(
        "AI-powered facility intelligence, "
        "water monitoring and predictive maintenance."
    )

    if st.button(
        "🔄 Refresh Data",
        width="stretch",
    ):
        st.rerun()

    st.divider()

    st.subheader("System Status")

    st.success("● Backend Online")
    st.success("● Database Connected")
    st.success("● Telemetry Ready")
    st.success("● AI Pipeline Ready")

    st.divider()

    st.caption("Database")

    st.code(
        str(DATABASE_PATH),
        language="text",
    )


# ============================================================
# LOAD TELEMETRY
# ============================================================

try:

    recent_readings = (
        repository.get_recent_readings(
            limit=500
        )
    )

except TypeError:

    recent_readings = (
        repository.get_recent_readings(
            500
        )
    )

except Exception:

    recent_readings = []


# ============================================================
# LOAD MAINTENANCE TICKETS
# ============================================================

try:

    open_tickets = (
        repository.get_open_maintenance_tickets()
    )

except Exception:

    open_tickets = []


try:

    ticket_history = (
        repository.get_maintenance_ticket_history(
            limit=100
        )
    )

except TypeError:

    ticket_history = (
        repository.get_maintenance_ticket_history(
            100
        )
    )

except Exception:

    ticket_history = []


# ============================================================
# CONVERT TO DATAFRAMES
# ============================================================

readings_df = readings_to_dataframe(
    recent_readings
)

open_tickets_df = tickets_to_dataframe(
    open_tickets
)

ticket_history_df = tickets_to_dataframe(
    ticket_history
)


# ============================================================
# KPI CALCULATIONS
# ============================================================

total_readings = len(
    readings_df
)

unique_facilities = (
    readings_df["Facility"].nunique()
    if not readings_df.empty
    else 0
)

unique_zones = (
    readings_df["Zone"].nunique()
    if not readings_df.empty
    else 0
)

unique_fixtures = (
    readings_df["Fixture"].nunique()
    if not readings_df.empty
    else 0
)

open_ticket_count = len(
    open_tickets_df
)

# ============================================================
# AI COPILOT
# ============================================================

st.header("🤖 AquaSense AI Copilot")

st.caption(
    "Ask questions about current maintenance incidents, "
    "telemetry, sensors, and fixtures. Responses are grounded "
    "in the AquaSense operational database."
)

copilot_question = st.text_input(
    "Ask AquaSense",
    placeholder=(
        "e.g. Are there any active maintenance issues?"
    ),
    key="copilot_question",
)

copilot_fixture_id = st.text_input(
    "Fixture ID (optional)",
    placeholder="Enter a fixture ID for a focused investigation",
    key="copilot_fixture_id",
)

if st.button(
    "Ask Copilot",
    type="primary",
    key="ask_copilot",
):
    if not copilot_question.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Analyzing AquaSense evidence..."):
            try:
                response = copilot_engine.answer(
                    copilot_question,
                    fixture_id=(
                        copilot_fixture_id.strip()
                        if copilot_fixture_id.strip()
                        else None
                    ),
                )

                st.markdown("### 💡 Copilot Response")

                st.info(response.answer)

                if response.confidence is not None:
                    st.caption(
                        f"Grounding confidence: "
                        f"{response.confidence:.0%}"
                    )

                if response.evidence:
                    with st.expander(
                        "🔎 View supporting evidence"
                    ):
                        for item in response.evidence:
                            st.markdown(
                                f"**Source:** `{item.source}`"
                            )

                            st.json(item.data)

            except Exception as exc:
                st.error(
                    "Copilot could not process the request."
                )
                st.exception(exc)

# ============================================================
# LIVE OPERATIONS
# ============================================================

st.header("Live Operations")

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Telemetry Readings",
        f"{total_readings:,}",
    )

with col2:

    st.metric(
        "Facilities",
        unique_facilities,
    )

with col3:

    st.metric(
        "Active Fixtures",
        unique_fixtures,
    )

with col4:

    st.metric(
        "Open Tickets",
        open_ticket_count,
    )


# ============================================================
# INCIDENT COMMAND CENTER
# ============================================================

st.subheader("🚨 Incident Command Center")

if open_tickets_df.empty:

    st.success(
        "No active maintenance incidents detected."
    )

    st.caption(
        "AquaSense is currently monitoring facility "
        "telemetry for abnormal operating conditions."
    )

else:

    # Display the highest-risk open ticket first.
    incident_df = (
        open_tickets_df
        .sort_values(
            "Risk Score",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    incident = incident_df.iloc[0]

    ticket_id = incident["Ticket ID"]
    anomaly = incident["Anomaly"]
    priority = incident["Priority"]
    risk_score = float(
        incident["Risk Score"]
        if pd.notna(incident["Risk Score"])
        else 0
    )

    facility = incident["Facility"]
    zone = incident["Zone"]
    fixture = incident["Fixture"]
    title = incident["Title"]
    description = incident["Description"]
    action = incident["Recommended Action"]

    evidence = normalize_evidence(
        incident["Evidence"]
    )

    # --------------------------------------------------------
    # Main incident card
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="incident-card">
            <div class="incident-title">
                🚨 {anomaly}
            </div>
            <div class="incident-subtitle">
                Active operational incident • Ticket {ticket_id}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Priority",
            priority,
        )

    with col2:
        st.metric(
            "Risk Score",
            f"{risk_score:.1f}/100",
        )

    with col3:
        st.metric(
            "Status",
            incident["Status"],
        )

    with col4:
        st.metric(
            "Ticket",
            ticket_id,
        )

    st.markdown("### 📍 Incident Location")

    location_col1, location_col2, location_col3 = st.columns(3)

    with location_col1:
        st.caption("Facility")
        st.write(facility)

    with location_col2:
        st.caption("Zone")
        st.write(zone)

    with location_col3:
        st.caption("Fixture")
        st.write(fixture)

    # --------------------------------------------------------
    # Why detected
    # --------------------------------------------------------

    st.markdown("### 🔎 Why AquaSense Flagged It")

    reason_col1, reason_col2 = st.columns(2)

    with reason_col1:

        st.markdown(
            """
            <div class="reason-card">

            <div class="reason-title">
            Explainable Decision Layer
            </div>

            <p>
            The anomaly was generated by the AquaSense
            operational detection pipeline rather than being
            presented as an unexplained black-box prediction.
            </p>

            <p>
            <b>Decision:</b>
            Active maintenance incident
            </p>

            </div>
            """,
            unsafe_allow_html=True,
        )

    with reason_col2:

        evidence_text = ""

        if evidence:

            evidence_lines = []

            for key, value in evidence.items():

                if isinstance(value, dict):
                    continue

                label = (
                    str(key)
                    .replace("_", " ")
                    .title()
                )

                evidence_lines.append(
                    f"• <b>{label}:</b> {value}"
                )

            if evidence_lines:

                evidence_text = (
                    "<br>".join(
                        evidence_lines[:8]
                    )
                )

        if not evidence_text:

            evidence_text = (
                "Detailed rule evidence is stored by the "
                "AquaSense backend and can be inspected from "
                "the maintenance record."
            )

        st.markdown(
            f"""
            <div class="reason-card">

            <div class="reason-title">
            Evidence
            </div>

            <p>
            {evidence_text}
            </p>

            </div>
            """,
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # Sustainability
    # --------------------------------------------------------

    st.markdown("### 💧 Sustainability Impact")

    litres_wasted = find_numeric_value(
        evidence,
        [
            "litres_wasted",
            "water_wasted_litres",
            "wasted_litres",
        ],
    )

    potential_saved = find_numeric_value(
        evidence,
        [
            "potential_litres_saved",
            "litres_saved",
            "potential_water_saved",
        ],
    )

    estimated_cost = find_numeric_value(
        evidence,
        [
            "estimated_cost",
            "cost",
            "estimated_water_cost",
        ],
    )

    potential_cost = find_numeric_value(
        evidence,
        [
            "potential_cost_saving",
            "cost_saving",
            "potential_saving",
        ],
    )

    if any(
        value is not None
        for value in [
            litres_wasted,
            potential_saved,
            estimated_cost,
            potential_cost,
        ]
    ):

        impact_col1, impact_col2, impact_col3, impact_col4 = (
            st.columns(4)
        )

        with impact_col1:
            st.markdown(
                f"""
                <div class="impact-card">
                    <div class="impact-value">
                        {litres_wasted:.2f} L
                    </div>
                    <div class="impact-label">
                        Estimated water wasted
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with impact_col2:
            st.markdown(
                f"""
                <div class="impact-card">
                    <div class="impact-value">
                        {potential_saved:.2f} L
                    </div>
                    <div class="impact-label">
                        Potential water saved
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with impact_col3:
            st.markdown(
                f"""
                <div class="impact-card">
                    <div class="impact-value">
                        ₹{estimated_cost:.2f}
                    </div>
                    <div class="impact-label">
                        Estimated cost impact
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with impact_col4:
            st.markdown(
                f"""
                <div class="impact-card">
                    <div class="impact-value">
                        ₹{potential_cost:.2f}
                    </div>
                    <div class="impact-label">
                        Potential cost saving
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    else:

        st.info(
            "Sustainability ledger values are not currently "
            "persisted inside the maintenance-ticket record. "
            "The sustainability engine remains available in "
            "the AquaSense backend."
        )

    # --------------------------------------------------------
    # Maintenance action
    # --------------------------------------------------------

    st.markdown("### 🛠 Recommended Maintenance Action")

    action_text = (
        action
        if action
        else "Inspect the affected fixture and resolve the active anomaly."
    )

    st.info(action_text)

    if description:

        with st.expander(
            "View incident description"
        ):

            st.write(description)


# ============================================================
# FACILITY STATUS
# ============================================================

st.subheader("Facility Status")

col1, col2 = st.columns(2)

with col1:

    st.markdown(
        """
        <div class="status-card">

        <div class="status-title">
        🟢 Operational Telemetry
        </div>

        <div class="status-description">
        AquaSense is connected to the facility
        telemetry data layer and ready to process
        incoming sensor readings.
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


with col2:

    if open_ticket_count == 0:

        maintenance_status = "🟢 Predictive Maintenance"

        maintenance_description = (
            "No open maintenance incidents. "
            "AquaSense continues monitoring fixture "
            "health and operational behavior."
        )

    else:

        maintenance_status = "🟠 Predictive Maintenance"

        maintenance_description = (
            f"{open_ticket_count} active maintenance "
            "incident(s) require attention."
        )

    st.markdown(
        f"""
        <div class="status-card">

        <div class="status-title">
        {maintenance_status}
        </div>

        <div class="status-description">
        {maintenance_description}
        </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# RECENT TELEMETRY
# ============================================================

st.subheader("Recent Telemetry")

if readings_df.empty:

    st.info(
        "No telemetry is currently stored in "
        "aquasense.db."
    )

    st.caption(
        "Run the AquaSense simulator against the "
        "dashboard database to populate this view."
    )

else:

    display_columns = [
        "Timestamp",
        "Zone",
        "Fixture",
        "Sensor Type",
        "Value",
        "Unit",
        "Diagnostic",
        "Quality",
    ]

    st.dataframe(
        readings_df[
            display_columns
        ].tail(100),
        width="stretch",
        hide_index=True,
    )


# ============================================================
# TELEMETRY SUMMARY
# ============================================================

if not readings_df.empty:

    st.subheader("Telemetry Summary")

    col1, col2 = st.columns(2)

    with col1:

        zone_counts = (
            readings_df["Zone"]
            .value_counts()
        )

        st.bar_chart(
            zone_counts,
            width="stretch",
        )

    with col2:

        sensor_counts = (
            readings_df["Sensor Type"]
            .value_counts()
        )

        st.bar_chart(
            sensor_counts,
            width="stretch",
        )


# ============================================================
# MAINTENANCE TICKETS
# ============================================================

st.subheader("Maintenance Tickets")

if open_tickets_df.empty:

    st.success(
        "No open maintenance tickets."
    )

else:

    display_columns = [
        "Ticket ID",
        "Zone",
        "Fixture",
        "Anomaly",
        "Priority",
        "Risk Score",
        "Status",
        "Created",
        "Title",
    ]

    st.dataframe(
        open_tickets_df[
            display_columns
        ],
        width="stretch",
        hide_index=True,
    )


# ============================================================
# TICKET HISTORY
# ============================================================

with st.expander(
    "View Maintenance Ticket History"
):

    if ticket_history_df.empty:

        st.info(
            "No maintenance ticket history available."
        )

    else:

        st.dataframe(
            ticket_history_df[
                [
                    "Ticket ID",
                    "Facility",
                    "Zone",
                    "Fixture",
                    "Anomaly",
                    "Priority",
                    "Risk Score",
                    "Status",
                    "Created",
                    "Title",
                ]
            ],
            width="stretch",
            hide_index=True,
        )


# ============================================================
# AI DECISION PIPELINE
# ============================================================

st.subheader("🧠 AquaSense AI Decision Pipeline")

pipeline_cols = st.columns(7)

pipeline_steps = [
    ("1", "IoT\nTelemetry"),
    ("2", "Feature\nEngineering"),
    ("3", "Rule + ML\nDetection"),
    ("4", "Decision\nFusion"),
    ("5", "Sustainability\nImpact"),
    ("6", "Maintenance\nRisk"),
    ("7", "Automatic\nTicket"),
]

for column, (number, label) in zip(
    pipeline_cols,
    pipeline_steps,
):

    with column:

        st.markdown(
            f"""
            <div class="pipeline-step">
                <b>{number}</b><br>
                {label.replace(chr(10), "<br>")}
            </div>
            """,
            unsafe_allow_html=True,
        )


st.caption(
    "Rules remain the authoritative operational decision "
    "layer. ML provides supporting statistical evidence."
)


# ============================================================
# SYSTEM ARCHITECTURE
# ============================================================

with st.expander(
    "View AquaSense AI Architecture"
):

    st.markdown(
        """
        ### AquaSense Decision Pipeline

        **IoT Telemetry**

        ↓

        **Feature Engineering**

        ↓

        **Explainable Rule Detection**

        +

        **Isolation Forest ML Detection**

        ↓

        **Rule + ML Fusion**

        ↓

        **Sustainability Impact**

        ↓

        **Predictive Maintenance Risk**

        ↓

        **Automated Maintenance Ticket**

        The operational rules remain the authoritative
        decision layer. ML provides supporting statistical
        evidence, while the future AI Copilot will narrate
        grounded operational data rather than making
        unsupported decisions.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "KOHLER AquaSense AI • Commercial Smart Facility "
    "& Sustainability Manager"
)

st.caption(
    "Phase 7B • Incident Command Dashboard"
)

st.caption(
    "Last refresh: "
    + datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
)
