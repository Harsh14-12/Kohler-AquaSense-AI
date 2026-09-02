from __future__ import annotations

from maintenance.schemas import (
    MaintenanceRiskInput,
    MaintenanceRiskLevel,
    MaintenanceRiskResult,
)


class MaintenanceRiskEngine:
    """
    Explainable predictive-maintenance risk engine.

    The engine uses a transparent weighted score rather than
    an opaque model.

    Maximum score = 100.

    Factors:

        anomaly frequency          20 points
        recent recurrence          20 points
        severity                   15 points
        sensor health              10 points
        abnormal flow              10 points
        persistence                15 points
        maintenance age             10 points

    This is a prototype decision-support model. The weights are
    engineering assumptions and are not KOHLER operational
    specifications.
    """

    MAX_SCORE = 100.0

    def calculate(
        self,
        data: MaintenanceRiskInput,
    ) -> MaintenanceRiskResult:
        """
        Calculate maintenance risk and explain the result.
        """

        factors = self._calculate_factors(data)

        risk_score = min(
            self.MAX_SCORE,
            sum(factors.values()),
        )

        risk_level = self._classify_risk(
            risk_score
        )

        action = self._recommended_action(
            risk_level
        )

        explanation = self._build_explanation(
            risk_level=risk_level,
            factors=factors,
        )

        return MaintenanceRiskResult(
            fixture_id=data.fixture_id,
            risk_score=round(
                risk_score,
                2,
            ),
            risk_level=risk_level,
            contributing_factors=factors,
            recommended_action=action,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Factor calculations
    # ------------------------------------------------------------------

    def _calculate_factors(
        self,
        data: MaintenanceRiskInput,
    ) -> dict[str, float]:
        """
        Calculate each risk contribution independently.

        Keeping factors separate makes the score auditable.
        """

        # --------------------------------------------------------------
        # Anomaly frequency — max 20
        # --------------------------------------------------------------

        anomaly_frequency = min(
            20.0,
            data.anomaly_count * 2.0,
        )

        # --------------------------------------------------------------
        # Recent recurrence — max 20
        # --------------------------------------------------------------

        recent_recurrence = min(
            20.0,
            data.recent_anomaly_count * 4.0,
        )

        # --------------------------------------------------------------
        # Severity — max 15
        # --------------------------------------------------------------

        severity_score = min(
            15.0,
            data.high_severity_anomaly_count * 5.0
            + data.critical_anomaly_count * 10.0,
        )

        # --------------------------------------------------------------
        # Sensor health — max 10
        #
        # Healthy sensor = 0 risk contribution.
        # Completely unhealthy sensor = 10.
        # --------------------------------------------------------------

        sensor_health_score = (
            1.0 - data.sensor_health
        ) * 10.0

        # --------------------------------------------------------------
        # Abnormal flow — max 10
        # --------------------------------------------------------------

        abnormal_flow_score = min(
            10.0,
            data.abnormal_flow_events * 2.0,
        )

        # --------------------------------------------------------------
        # Persistence — max 15
        #
        # 60+ persistent minutes reaches maximum contribution.
        # --------------------------------------------------------------

        persistence_score = min(
            15.0,
            data.persistent_anomaly_minutes
            / 4.0,
        )

        # --------------------------------------------------------------
        # Maintenance age — max 10
        #
        # 180+ days reaches maximum contribution.
        # --------------------------------------------------------------

        maintenance_age_score = min(
            10.0,
            data.days_since_last_maintenance
            / 18.0,
        )

        return {
            "anomaly_frequency": round(
                anomaly_frequency,
                2,
            ),
            "recent_recurrence": round(
                recent_recurrence,
                2,
            ),
            "severity": round(
                severity_score,
                2,
            ),
            "sensor_health": round(
                sensor_health_score,
                2,
            ),
            "abnormal_flow": round(
                abnormal_flow_score,
                2,
            ),
            "persistence": round(
                persistence_score,
                2,
            ),
            "maintenance_age": round(
                maintenance_age_score,
                2,
            ),
        }

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify_risk(
        self,
        score: float,
    ) -> MaintenanceRiskLevel:
        """
        Convert numerical risk into an operational category.
        """

        if score >= 80.0:
            return MaintenanceRiskLevel.CRITICAL

        if score >= 60.0:
            return MaintenanceRiskLevel.HIGH

        if score >= 30.0:
            return MaintenanceRiskLevel.MEDIUM

        return MaintenanceRiskLevel.LOW

    # ------------------------------------------------------------------
    # Recommended action
    # ------------------------------------------------------------------

    def _recommended_action(
        self,
        level: MaintenanceRiskLevel,
    ) -> str:
        """
        Generate an operational recommendation.
        """

        actions = {
            MaintenanceRiskLevel.LOW: (
                "Continue monitoring. No immediate "
                "maintenance action required."
            ),
            MaintenanceRiskLevel.MEDIUM: (
                "Review fixture telemetry and schedule "
                "preventive inspection if the pattern persists."
            ),
            MaintenanceRiskLevel.HIGH: (
                "Create a priority maintenance ticket and "
                "inspect the fixture at the next available window."
            ),
            MaintenanceRiskLevel.CRITICAL: (
                "Dispatch maintenance immediately and inspect "
                "the fixture for active failure or water loss."
            ),
        }

        return actions[level]

    # ------------------------------------------------------------------
    # Explanation
    # ------------------------------------------------------------------

    def _build_explanation(
        self,
        risk_level: MaintenanceRiskLevel,
        factors: dict[str, float],
    ) -> str:
        """
        Explain which factors contributed most strongly
        to the maintenance-risk score.
        """

        significant = [
            (name, value)
            for name, value in factors.items()
            if value > 0.0
        ]

        significant.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        if not significant:
            return (
                "No significant maintenance-risk indicators "
                "were detected."
            )

        top_factors = significant[:3]

        factor_text = ", ".join(
            f"{name}={value:.1f}"
            for name, value in top_factors
        )

        return (
            f"Maintenance risk classified as "
            f"{risk_level.value}. "
            f"Primary contributing factors: "
            f"{factor_text}."
        )