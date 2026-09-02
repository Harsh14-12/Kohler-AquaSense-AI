from __future__ import annotations

from typing import List

import numpy as np
from sklearn.ensemble import IsolationForest

from features.schemas import FeatureVector

from .schemas import MLAnomalyResult


class IsolationForestDetector:
    """
    Unsupervised multivariate anomaly detector.

    The detector is trained on historical FeatureVector records
    representing normal operating behaviour.

    Isolation Forest is used because labelled fault data is not
    required for training.
    """

    DEFAULT_FEATURES = [
        "current_flow_rate",
        "average_flow_rate",
        "flow_variance",
        "flow_change",
        "occupancy",
        "flush_rate",
        "usage_per_occupant",
        "idle_flow_minutes",
        "time_since_last_flush",
        "time_since_last_usage",
        "baseline_flow",
        "baseline_deviation",
        "baseline_deviation_sigma",
        "diagnostic_health",
    ]

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        if not 0.0 < contamination < 0.5:
            raise ValueError(
                "contamination must be between 0 and 0.5"
            )

        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state

        self._model: IsolationForest | None = None
        self._feature_names: List[str] = list(
            self.DEFAULT_FEATURES
        )

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def _vectorize(
        self,
        feature: FeatureVector,
    ) -> List[float]:
        """
        Convert a FeatureVector into a deterministic numerical vector.
        """

        values: List[float] = []

        for name in self._feature_names:
            value = getattr(feature, name)

            if value is None:
                value = 0.0

            values.append(float(value))

        return values

    def _matrix(
        self,
        features: List[FeatureVector],
    ) -> np.ndarray:
        """
        Convert FeatureVector objects into a NumPy matrix.
        """

        if not features:
            raise ValueError(
                "At least one feature vector is required."
            )

        return np.asarray(
            [
                self._vectorize(feature)
                for feature in features
            ],
            dtype=float,
        )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def fit(
        self,
        features: List[FeatureVector],
    ) -> "IsolationForestDetector":
        """
        Train the Isolation Forest on historical observations.
        """

        if len(features) < 10:
            raise ValueError(
                "At least 10 feature vectors are required "
                "to train the anomaly detector."
            )

        matrix = self._matrix(features)

        self._model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
        )

        self._model.fit(matrix)

        return self

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        feature: FeatureVector,
    ) -> MLAnomalyResult:
        """
        Predict whether a FeatureVector is anomalous.
        """

        if self._model is None:
            raise RuntimeError(
                "Detector has not been trained. "
                "Call fit() before predict()."
            )

        vector = np.asarray(
            [self._vectorize(feature)],
            dtype=float,
        )

        prediction = int(
            self._model.predict(vector)[0]
        )

        raw_score = float(
            self._model.decision_function(vector)[0]
        )

        # Isolation Forest returns larger decision-function
        # values for more normal observations.
        #
        # Convert the value into a simple anomaly score where
        # larger means more anomalous.
        anomaly_score = max(
            0.0,
            min(
                1.0,
                0.5 - raw_score,
            ),
        )

        is_anomaly = prediction == -1

        if is_anomaly:
            confidence = min(
                1.0,
                0.5 + anomaly_score,
            )
            explanation = (
                "The multivariate operating pattern differs "
                "from the learned normal behaviour."
            )
        else:
            confidence = max(
                0.0,
                1.0 - anomaly_score,
            )
            explanation = (
                "The multivariate operating pattern is "
                "consistent with learned normal behaviour."
            )

        return MLAnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=confidence,
            model_name="IsolationForest",
            features_used=list(
                self._feature_names
            ),
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Model status
    # ------------------------------------------------------------------

    @property
    def is_fitted(self) -> bool:
        """
        Return True when the detector has been trained.
        """

        return self._model is not None

    @property
    def feature_names(self) -> List[str]:
        """
        Return the feature names used by the detector.
        """

        return list(self._feature_names)