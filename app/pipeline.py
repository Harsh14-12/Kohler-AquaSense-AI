from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from detection.rule_engine import RuleEngine
from detection.schemas import AnomalyEvent
from features.feature_engine import FeatureEngine
from fusion.fusion_engine import FusionEngine
from fusion.schemas import FusionResult
from maintenance.risk_builder import MaintenanceRiskBuilder
from maintenance.risk_engine import MaintenanceRiskEngine
from maintenance.schemas import MaintenanceRiskInput, MaintenanceRiskResult
from maintenance.ticket_engine import MaintenanceTicketEngine
from maintenance.ticket_schemas import MaintenanceTicket
from ml.anomaly_detector import IsolationForestDetector
from ml.schemas import MLAnomalyResult
from schemas.telemetry import SensorReading
from sustainability.impact_engine import SustainabilityImpactEngine
from sustainability.schemas import SustainabilityImpact


@dataclass
class PipelineResult:
    """Result produced by one end-to-end AquaSense pipeline step."""

    feature_vector: object
    rule_event: Optional[AnomalyEvent]
    ml_result: Optional[MLAnomalyResult]
    fusion_result: FusionResult
    sustainability_impact: Optional[SustainabilityImpact]
    risk_input: Optional[MaintenanceRiskInput]
    risk_result: Optional[MaintenanceRiskResult]
    maintenance_ticket: Optional[MaintenanceTicket]
    ticket_created: bool


class AquaSensePipeline:
    """
    End-to-end AquaSense backend pipeline.

    Processing flow:

        SensorReading
            ↓
        Feature Engineering
            ↓
        Rule Detection
            ↓
        ML Detection
            ↓
        Rule + ML Fusion
            ↓
        Sustainability Impact
            ↓
        Maintenance Risk
            ↓
        Maintenance Ticket
    """

    def __init__(
        self,
        feature_engine: Optional[FeatureEngine] = None,
        rule_engine: Optional[RuleEngine] = None,
        ml_detector: Optional[IsolationForestDetector] = None,
        fusion_engine: Optional[FusionEngine] = None,
        sustainability_engine: Optional[SustainabilityImpactEngine] = None,
        risk_builder: Optional[MaintenanceRiskBuilder] = None,
        risk_engine: Optional[MaintenanceRiskEngine] = None,
        ticket_engine: Optional[MaintenanceTicketEngine] = None,
    ) -> None:
        self.feature_engine = feature_engine or FeatureEngine()
        self.rule_engine = rule_engine or RuleEngine()
        self.ml_detector = ml_detector or IsolationForestDetector()
        self.fusion_engine = fusion_engine or FusionEngine()
        self.sustainability_engine = (
            sustainability_engine or SustainabilityImpactEngine()
        )
        self.risk_builder = risk_builder or MaintenanceRiskBuilder()
        self.risk_engine = risk_engine or MaintenanceRiskEngine()
        self.ticket_engine = ticket_engine or MaintenanceTicketEngine()

        self._anomaly_history: list[AnomalyEvent] = []

    @property
    def anomaly_history(self) -> list[AnomalyEvent]:
        """Return a copy of all rule-generated anomaly events."""
        return list(self._anomaly_history)

    def process_reading(
        self,
        reading: SensorReading,
        ml_training_vectors: Optional[Sequence[object]] = None,
        sensor_health: float = 1.0,
        days_since_last_maintenance: float = 0.0,
    ) -> PipelineResult:
        """
        Process one telemetry reading through the complete pipeline.

        Parameters
        ----------
        reading:
            Incoming sensor telemetry.

        ml_training_vectors:
            Optional healthy FeatureVector history used to train
            the Isolation Forest detector.

        sensor_health:
            Current sensor health score from 0 to 1.

        days_since_last_maintenance:
            Number of days since the fixture was last serviced.
        """

        # ---------------------------------------------------------
        # 1. Feature engineering
        # ---------------------------------------------------------
        feature_vector = self.feature_engine.update(reading)

        # ---------------------------------------------------------
        # 2. Deterministic rule detection
        # ---------------------------------------------------------
        rule_events = self.rule_engine.evaluate(feature_vector)

        rule_event: Optional[AnomalyEvent] = (
            rule_events[0] if rule_events else None
        )

        # ---------------------------------------------------------
        # 3. ML anomaly detection
        # ---------------------------------------------------------
        ml_result: Optional[MLAnomalyResult] = None

        if ml_training_vectors:
            self.ml_detector.fit(list(ml_training_vectors))
            ml_result = self.ml_detector.predict(feature_vector)

        # ---------------------------------------------------------
        # 4. Rule + ML fusion
        # ---------------------------------------------------------
        fusion_result = self.fusion_engine.combine(
            rule_event,
            ml_result,
        )

        # ---------------------------------------------------------
        # No rule anomaly:
        # do not create downstream operational actions.
        # ---------------------------------------------------------
        if rule_event is None:
            return PipelineResult(
                feature_vector=feature_vector,
                rule_event=None,
                ml_result=ml_result,
                fusion_result=fusion_result,
                sustainability_impact=None,
                risk_input=None,
                risk_result=None,
                maintenance_ticket=None,
                ticket_created=False,
            )

        # ---------------------------------------------------------
        # 5. Store anomaly history
        # ---------------------------------------------------------
        self._anomaly_history.append(rule_event)

        # ---------------------------------------------------------
        # 6. Sustainability impact
        # ---------------------------------------------------------
        sustainability_impact = self.sustainability_engine.calculate(
            rule_event
        )

        # ---------------------------------------------------------
        # 7. Maintenance risk
        # ---------------------------------------------------------
        risk_input = self.risk_builder.build(
            fixture_id=rule_event.fixture_id,
            events=self._anomaly_history,
            reference_time=rule_event.timestamp,
            sensor_health=sensor_health,
            days_since_last_maintenance=days_since_last_maintenance,
        )

        risk_result = self.risk_engine.calculate(risk_input)

                # ---------------------------------------------------------
        # 8. Maintenance ticket
        # ---------------------------------------------------------
        maintenance_ticket, ticket_created = (
            self.ticket_engine.create_or_get_ticket(
                rule_event,
                risk_result,
                created_at=rule_event.timestamp,
            )
        )

        # ---------------------------------------------------------
        # 9. Attach sustainability impact to ticket evidence
        # ---------------------------------------------------------
        #
        # The sustainability engine calculates the values, but
        # the maintenance ticket is the object persisted by the
        # current demo workflow. Store the calculated values in
        # ticket evidence so the dashboard can display the same
        # numbers without hard-coding them.
        #
        # This keeps the architecture:
        #
        # Anomaly -> Sustainability Engine -> Ticket Evidence
        #                              -> Dashboard
        #
        # rather than:
        #
        # Anomaly -> hard-coded dashboard numbers
        #
        sustainability_evidence = {
            "litres_wasted": sustainability_impact.litres_wasted,
            "potential_litres_saved": (
                sustainability_impact.potential_litres_saved
            ),
            "estimated_cost": sustainability_impact.estimated_cost,
            "potential_cost_saving": (
                sustainability_impact.potential_cost_saving
            ),
            "estimated_co2e_kg": (
                sustainability_impact.estimated_co2e_kg
            ),
            "excess_flow_litres_per_minute": (
                sustainability_impact.excess_flow_litres_per_minute
            ),
            "duration_minutes": (
                sustainability_impact.duration_minutes
            ),
            "calculation_trace": (
                sustainability_impact.calculation_trace
            ),
        }

        if maintenance_ticket.evidence is None:
            maintenance_ticket.evidence = {}

        maintenance_ticket.evidence[
            "sustainability_impact"
        ] = sustainability_evidence

        return PipelineResult(
            feature_vector=feature_vector,
            rule_event=rule_event,
            ml_result=ml_result,
            fusion_result=fusion_result,
            sustainability_impact=sustainability_impact,
            risk_input=risk_input,
            risk_result=risk_result,
            maintenance_ticket=maintenance_ticket,
            ticket_created=ticket_created,
        )