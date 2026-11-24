import numpy as np
from backend.config import settings

class HotspotService:
    def __init__(self):
        pass

    def detect_hotspots_baseline(self, ndvi_array, ndmi_array, ndre_array, temporal_deviation=None):
        """
        BASELINE HEURISTIC anomaly detector.
        This is NOT an AI/ML model — it's a simple weighted scoring formula.
        Used as the default detection method.
        """
        if temporal_deviation is None:
            temporal_deviation = np.zeros_like(ndvi_array)
            
        w1, w2, w3, w4 = settings.NDVI_WEIGHT, settings.NDMI_WEIGHT, settings.NDRE_WEIGHT, settings.TEMPORAL_WEIGHT
        
        # Normalize arrays 0-1 assuming ranges
        norm_ndvi = np.clip(ndvi_array, 0, 1)
        norm_ndmi = np.clip((ndmi_array + 1) / 2, 0, 1)
        norm_ndre = np.clip(ndre_array, 0, 1)
        
        health_score = (
            w1 * norm_ndvi +
            w2 * norm_ndmi +
            w3 * norm_ndre -
            w4 * np.abs(temporal_deviation)
        )
        
        health_score_100 = health_score * 100
        return health_score_100

    def detect_hotspots_ml(self, feature_matrix):
        """
        ML-based anomaly detection using Isolation Forest (scikit-learn).
        This is the actual AI/ML model for the project.
        Requires sufficient data points to be meaningful.
        """
        from sklearn.ensemble import IsolationForest
        clf = IsolationForest(contamination=0.1, random_state=42)
        preds = clf.fit_predict(feature_matrix)
        # -1 indicates anomaly, 1 indicates normal
        return preds
