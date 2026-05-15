"""
evaluation.py — Model Evaluation & Visualization

Metrics: Accuracy, F1-score, PR-AUC (class-imbalance-aware).
Plots:   PR curves, learning curves, regularization paths, sparsity analysis.
"""

import os
import logging

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    f1_score,
    accuracy_score,
    precision_recall_curve,
    average_precision_score,
    classification_report,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")


# ── Core metric evaluation ────────────────────────────────────────────────────

def evaluate_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    label: str = "model",
    save_dir: str | None = None,
) -> dict:
    """
    Compute Accuracy, F1-score, PR-AUC and save a PR curve.

    Returns dict with keys: label, accuracy, f1_score, pr_auc
    """
    if save_dir is None:
        save_dir = RESULTS_DIR
    os.makedirs(save_dir, exist_ok=True)

    acc    = accuracy_score(y_true, y_pred)
    f1     = f1_score(y_true, y_pred, zero_division=0)
    pr_auc = average_precision_score(y_true, y_proba)

    logger.info("[%s] Acc=%.4f | F1=%.4f | PR-AUC=%.4f", label, acc, f1, pr_auc)
    logger.debug("Classification Report:\n%s",
                 classification_report(y_true, y_pred, zero_division=0))

    _save_pr_curve(y_true, y_proba, label, pr_auc, save_dir)
    return {"label": label, "accuracy": acc, "f1_score": f1, "pr_auc": pr_auc}


def _save_pr_curve(y_true, y_proba, label, pr_auc, save_dir):
    precision, recall, _ = precision_recall_curve(y_true, y_proba)

    sns.set_theme(style="whitegrid", font_scale=1.1)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(recall, precision, linewidth=2, color="#2196F3",
            label=f"PR Curve (AUC = {pr_auc:.4f})")
    ax.fill_between(recall, precision, alpha=0.15, color="#2196F3")
    ax.set_xlabel("Recall", fontsize=12)
    ax.set_ylabel("Precision", fontsize=12)
    ax.set_title(f"Precision-Recall Curve -- {label}", fontsize=14)
    ax.legend(loc="lower left", fontsize=10)
    ax.set_xlim([0.0, 1.05])
    ax.set_ylim([0.0, 1.05])

    safe = label.replace(" ", "_").replace("/", "_")
    path = os.path.join(save_dir, f"pr_curve_{safe}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("PR curve -> %s", path)


# ── Requirement 4: Learning curves ───────────────────────────────────────────

def plot_learning_curves(
    estimator,
    X: np.ndarray,
    y: np.ndarray,
    label: str,
    save_dir: str | None = None,
    cv: int = 5,
) -> None:
    """
    Plot train vs cross-val F1 against training set size.

    A large train-val gap at high sizes -> overfitting.
    Both curves low -> underfitting.
    Curves converging high -> good generalisation.
    """
    from sklearn.model_selection import learning_curve, StratifiedKFold

    if save_dir is None:
        save_dir = RESULTS_DIR
    os.makedirs(save_dir, exist_ok=True)

    n_min    = int(min(np.bincount(y.astype(int))))
    n_splits = max(2, min(cv, n_min))
    cv_obj   = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    min_frac   = max(0.1, (n_splits * 2) / (n_min * 0.8 + 1))
    train_sizes = np.linspace(min(min_frac, 0.5), 1.0, 10)

    sizes_abs, tr_scores, val_scores = learning_curve(
        estimator, X, y,
        cv=cv_obj,
        scoring="f1",
        train_sizes=train_sizes,
        error_score=0.0,
    )

    tr_mean,  tr_std  = tr_scores.mean(1),  tr_scores.std(1)
    val_mean, val_std = val_scores.mean(1), val_scores.std(1)

    sns.set_theme(style="whitegrid", font_scale=1.1)
    fig, ax = plt.subplots(figsize=(9, 6))

    ax.plot(sizes_abs, tr_mean,  "o-", color="#E53935", lw=2, label="Training F1")
    ax.fill_between(sizes_abs, tr_mean - tr_std,  tr_mean + tr_std,
                    alpha=0.15, color="#E53935")
    ax.plot(sizes_abs, val_mean, "o-", color="#1E88E5", lw=2, label="Cross-Val F1")
    ax.fill_between(sizes_abs, val_mean - val_std, val_mean + val_std,
                    alpha=0.15, color="#1E88E5")

    ax.set_xlabel("Training Set Size", fontsize=12)
    ax.set_ylabel("F1 Score", fontsize=12)
    ax.set_title(f"Learning Curves -- {label}", fontsize=14)
    ax.legend(loc="lower right", fontsize=10)
    ax.set_ylim([0.0, 1.05])

    safe = label.replace(" ", "_").replace("/", "_")
    path = os.path.join(save_dir, f"learning_curve_{safe}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Learning curve -> %s", path)


# ── Requirement 4: Regularization path (overfitting/underfitting) ─────────────

def plot_regularization_path(
    X_train: np.ndarray,
    X_test: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    label: str,
    save_dir: str | None = None,
) -> None:
    """
    Sweep C (inverse regularisation strength) from 1e-4 to 1e3.

    Low  C -> strong regularisation -> underfitting (both curves low).
    High C -> weak  regularisation -> overfitting  (train-val gap grows).
    """
    from sklearn.linear_model import LogisticRegression

    if save_dir is None:
        save_dir = RESULTS_DIR
    os.makedirs(save_dir, exist_ok=True)

    C_values  = np.logspace(-4, 3, 20)
    train_f1s, val_f1s = [], []

    for C in C_values:
        model = LogisticRegression(
            C=C, l1_ratio=0.0, solver="saga", max_iter=3000, random_state=42
        )
        model.fit(X_train, y_train)
        train_f1s.append(f1_score(y_train, model.predict(X_train), zero_division=0))
        val_f1s.append(  f1_score(y_test,  model.predict(X_test),  zero_division=0))

    sns.set_theme(style="whitegrid", font_scale=1.1)
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.semilogx(C_values, train_f1s, "o-", color="#E53935", lw=2, ms=5, label="Train F1")
    ax.semilogx(C_values, val_f1s,   "o-", color="#1E88E5", lw=2, ms=5, label="Validation F1")
    ax.axvspan(C_values[0], 5e-3,        alpha=0.07, color="steelblue", label="Underfitting zone")
    ax.axvspan(2e2,         C_values[-1], alpha=0.07, color="salmon",    label="Overfitting zone")

    ax.set_xlabel("C  (Inverse Regularisation Strength - log scale)", fontsize=12)
    ax.set_ylabel("F1 Score", fontsize=12)
    ax.set_title(
        f"Regularisation Path -- {label}\n"
        "Low C = Underfitting  |  High C = Overfitting",
        fontsize=12,
    )
    ax.legend(loc="lower right", fontsize=10)
    ax.set_ylim([0.0, 1.05])

    safe = label.replace(" ", "_").replace("/", "_")
    path = os.path.join(save_dir, f"reg_path_{safe}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Regularisation path -> %s", path)


# ── Requirement 5: Sparsity analysis ─────────────────────────────────────────

def plot_sparsity_analysis(
    X_train: np.ndarray,
    y_train: np.ndarray,
    label: str,
    save_dir: str | None = None,
) -> dict:
    """
    Fit L1, ElasticNet, L2 LR models on identical data.
    Plot sorted |coefficient| magnitudes for each to show L1's
    feature-selection effect vs L2's dense-shrinkage solution.

    Returns dict mapping model name -> non-zero coefficient count.
    """
    from sklearn.linear_model import LogisticRegression

    if save_dir is None:
        save_dir = RESULTS_DIR
    os.makedirs(save_dir, exist_ok=True)

    configs = [
        ("L1 (Lasso)\nl1_ratio=1.0",   1.0, "#E53935"),
        ("ElasticNet\nl1_ratio=0.5",    0.5, "#7B1FA2"),
        ("L2 (Ridge)\nl1_ratio=0.0",    0.0, "#1E88E5"),
    ]

    sns.set_theme(style="whitegrid", font_scale=1.0)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    stats = {}
    for ax, (name, l1_ratio, color) in zip(axes, configs):
        model = LogisticRegression(
            C=1.0, l1_ratio=l1_ratio, solver="saga", max_iter=3000, random_state=42
        )
        model.fit(X_train, y_train)

        coefs        = np.abs(model.coef_[0])
        sorted_coefs = np.sort(coefs)[::-1]
        nonzero      = int(np.sum(coefs > 1e-4))
        short_name   = name.split("\n")[0].strip()
        stats[short_name] = nonzero

        plot_vals = np.maximum(sorted_coefs, 1e-8)   # floor for log scale
        ax.bar(range(len(plot_vals)), plot_vals, color=color, alpha=0.75, width=1.0)
        ax.set_yscale("log")
        ax.set_title(f"{name}\nNon-zero: {nonzero} / {len(coefs)}", fontsize=11)
        ax.set_xlabel("Feature index (sorted by |coef|)", fontsize=9)
        ax.set_ylabel("|Coefficient|  (log scale)", fontsize=9)
        ax.grid(True, alpha=0.3, axis="y")

        logger.info("  %-18s  non-zero=%d/%d  (%.1f%% sparse)",
                    short_name, nonzero, len(coefs),
                    100 * (1 - nonzero / max(len(coefs), 1)))

    fig.suptitle(
        f"Coefficient Sparsity: L1 vs ElasticNet vs L2 -- {label}\n"
        "L1 zeros-out irrelevant features; L2 shrinks all uniformly",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()

    safe = label.replace(" ", "_").replace("/", "_")
    path = os.path.join(save_dir, f"sparsity_{safe}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Sparsity plot -> %s", path)
    return stats


# ── CSV persistence ───────────────────────────────────────────────────────────

def save_results_csv(results: list[dict], path: str | None = None) -> str:
    import pandas as pd

    if path is None:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        path = os.path.join(RESULTS_DIR, "comparison_results.csv")

    df = pd.DataFrame(results)
    df.to_csv(path, index=False)
    logger.info("Results CSV -> %s  (%d rows)", path, len(df))
    return path
