from sklearn.ensemble import IsolationForest
import numpy as np

class IsolationForestDetector:
    """
    Isolation Forest anomaly detector wrapper.
    This is the actual AI/ML component of the system.
    """
    def __init__(self, contamination=0.1, random_state=42):
        self.model = IsolationForest(contamination=contamination, random_state=random_state)
        self.is_fitted = False
        
    def fit(self, feature_matrix):
        """Fit the model to the feature matrix."""
        self.model.fit(feature_matrix)
        self.is_fitted = True
        return self
        
    def predict(self, feature_matrix):
        """Predict anomalies. Returns -1 for anomalies and 1 for normal points."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before calling predict.")
        return self.model.predict(feature_matrix)
        
    def explain_anomaly(self, feature_values):
        """Generates human-readable explanations for an anomaly."""
        return "Anomaly detected by Isolation Forest based on multivariate deviations in vegetation indices."
