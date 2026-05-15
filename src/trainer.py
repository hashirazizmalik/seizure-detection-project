"""
trainer.py — Logistic Regression Training Engine

Supports L1, L2, and ElasticNet regularisation with three imbalance strategies:
  - SMOTE oversampling
  - Random undersampling
  - Class weighting (passed directly to LogisticRegression)
"""

import logging
import numpy as np
from sklearn.linear_model import LogisticRegression
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler

logger = logging.getLogger(__name__)

# sklearn 1.8+: use l1_ratio instead of deprecated penalty parameter.
# l1_ratio=1.0 -> pure L1 (Lasso)
# l1_ratio=0.0 -> pure L2 (Ridge)
# 0 < l1_ratio < 1 -> ElasticNet
_PENALTY_TO_L1_RATIO = {"l1": 1.0, "l2": 0.0, "elasticnet": 0.5}


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    penalty: str = "l2",
    C: float = 1.0,
    use_smote: bool = False,
    use_undersample: bool = False,
    class_weight: str | None = None,
    max_iter: int = 5000,
    random_state: int = 42,
) -> LogisticRegression:
    """
    Train a Logistic Regression model.

    Args:
        X_train:         Training features.
        y_train:         Training labels (binary).
        penalty:         'l1', 'l2', or 'elasticnet' (mapped to l1_ratio).
        C:               Inverse regularisation strength (smaller = stronger).
        use_smote:       Apply SMOTE oversampling before training.
        use_undersample: Apply random undersampling before training.
        class_weight:    None or 'balanced' for implicit class weighting.
        max_iter:        Max solver iterations.
        random_state:    Random seed for reproducibility.

    Returns:
        Fitted LogisticRegression model.
    """
    n_original = len(y_train)

    # ── Imbalance handling ────────────────────────────────────────────────────
    if use_smote:
        n_minority = int(min(np.bincount(y_train)))
        if n_minority < 2:
            logger.warning("Too few minority samples (%d) for SMOTE. Skipping.", n_minority)
        else:
            k_neighbors = min(5, n_minority - 1)
            smote = SMOTE(k_neighbors=k_neighbors, random_state=random_state)
            try:
                X_train, y_train = smote.fit_resample(X_train, y_train)
                logger.info("SMOTE: %d -> %d samples.", n_original, len(y_train))
            except Exception as exc:
                logger.warning("SMOTE failed: %s. Training without it.", exc)

    elif use_undersample:
        n_minority = int(min(np.bincount(y_train)))
        if n_minority < 5:
            logger.warning("Too few minority samples (%d) for undersampling. Skipping.", n_minority)
        else:
            rus = RandomUnderSampler(random_state=random_state)
            try:
                X_train, y_train = rus.fit_resample(X_train, y_train)
                logger.info("UnderSample: %d -> %d samples.", n_original, len(y_train))
            except Exception as exc:
                logger.warning("Undersampling failed: %s. Training without it.", exc)

    # ── Model training ────────────────────────────────────────────────────────
    l1_ratio = _PENALTY_TO_L1_RATIO.get(penalty, 0.0)

    model = LogisticRegression(
        C=C,
        l1_ratio=l1_ratio,
        solver="saga",
        class_weight=class_weight,
        max_iter=max_iter,
        random_state=random_state,
    )

    logger.info(
        "Training LR(penalty=%s, l1_ratio=%.1f, C=%.4f, class_weight=%s)",
        penalty, l1_ratio, C, class_weight,
    )
    model.fit(X_train, y_train)
    return model
