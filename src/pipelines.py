"""
pipelines.py — Preprocessing Pipeline Definitions

Pipeline A: Normalization -> Noise Removal -> Feature Selection
Pipeline B: Feature Extraction -> Scaling -> PCA
"""

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_classif
from scipy.signal import butter, sosfiltfilt
from scipy.stats import skew, kurtosis


class BandpassFilter(BaseEstimator, TransformerMixin):
    """Noise removal via Butterworth bandpass filter (0.5-50 Hz)."""

    def __init__(self, low=0.5, high=50.0, fs=173.6, order=4):
        self.low = low
        self.high = high
        self.fs = fs
        self.order = order

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        Xf = np.copy(X)
        ny = self.fs / 2.0
        lo = max(self.low / ny, 0.01)
        hi = min(self.high / ny, 0.99)
        if lo >= hi:
            return Xf
        try:
            sos = butter(self.order, [lo, hi], btype="band", output="sos")
        except ValueError:
            return Xf
        for i in range(Xf.shape[0]):
            if Xf.shape[1] > 12:
                try:
                    Xf[i] = sosfiltfilt(sos, Xf[i])
                except ValueError:
                    pass
        return Xf


class StatisticalFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extract statistical features: mean, std, skew, kurtosis, energy, etc."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        feats = []
        for row in X:
            feats.append([
                np.mean(row), np.std(row),
                float(skew(row)), float(kurtosis(row)),
                np.sum(row ** 2),
                np.max(np.abs(row)), np.min(row), np.ptp(row),
                np.sum(np.diff(np.sign(row)) != 0) / len(row),
            ])
        return np.array(feats, dtype=np.float64)


def build_pipeline_a(k_features=50):
    """Pipeline A: MinMaxScaler -> BandpassFilter -> SelectKBest."""
    return Pipeline([
        ("normalize", MinMaxScaler()),
        ("denoise", BandpassFilter()),
        ("feature_select", SelectKBest(score_func=f_classif, k=k_features)),
    ])


def build_pipeline_b(n_components=8):
    """Pipeline B: StatisticalFeatureExtractor -> StandardScaler -> PCA."""
    return Pipeline([
        ("extract", StatisticalFeatureExtractor()),
        ("scale", StandardScaler()),
        ("pca", PCA(n_components=n_components)),
    ])


PIPELINE_BUILDERS = {
    "Pipeline_A": build_pipeline_a,
    "Pipeline_B": build_pipeline_b,
}
