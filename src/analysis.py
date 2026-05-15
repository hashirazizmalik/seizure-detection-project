"""
analysis.py -- Comparative Analysis Plots (Requirement 7)

Answers the four research questions:
  Q1. Does preprocessing order affect results?
  Q2. Which regularisation generalises best across datasets?
  Q3. Does ElasticNet consistently outperform L1 / L2?
  Q4. How does imbalance handling interact with regularisation?
"""

import os
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")


def _save(fig, filename: str, save_dir: str) -> None:
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved -> %s", path)


def _label_bars(ax, fmt=".3f"):
    for bar in ax.patches:
        h = bar.get_height()
        if h > 0.005:
            ax.text(
                bar.get_x() + bar.get_width() / 2, h + 0.015,
                f"{h:{fmt}}", ha="center", va="bottom", fontsize=8,
            )


# ── Q1: Pipeline comparison ───────────────────────────────────────────────────

def plot_pipeline_comparison(df: pd.DataFrame, save_dir: str | None = None) -> None:
    """
    Q1: Bar chart -- Pipeline A vs Pipeline B per dataset.

    Pipeline A (Normalise -> Denoise -> SelectKBest) vs
    Pipeline B (Statistical features -> Scale -> PCA).
    Shows how preprocessing order changes model performance.
    """
    if save_dir is None:
        save_dir = RESULTS_DIR

    sns.set_theme(style="whitegrid", font_scale=1.1)
    palette = {"Pipeline_A": "#1E88E5", "Pipeline_B": "#E53935"}
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, (metric, ylabel) in zip(
        axes, [("f1_score", "Mean F1 Score"), ("pr_auc", "Mean PR-AUC")]
    ):
        agg = df.groupby(["dataset", "pipeline"])[metric].mean().reset_index()
        sns.barplot(
            data=agg, x="dataset", y=metric, hue="pipeline",
            palette=palette, ax=ax, edgecolor="black", linewidth=0.5,
        )
        _label_bars(ax)
        ax.set_title(f"Pipeline A vs B -- {ylabel}", fontsize=13)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xlabel("Dataset", fontsize=11)
        ax.set_ylim([0, 1.15])
        ax.legend(title="Pipeline", fontsize=9)

    fig.suptitle(
        "Q1: Does Preprocessing Order Affect Results?\n"
        "Pipeline B (feature extraction path) vs Pipeline A (raw signal path)",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "analysis_q1_pipeline_comparison.png", save_dir)


# ── Q2 / Q3: Regularisation comparison ───────────────────────────────────────

def plot_regularization_comparison(df: pd.DataFrame, save_dir: str | None = None) -> None:
    """
    Q2/Q3: Group bar chart -- L1 vs L2 vs ElasticNet per dataset.

    Shows which regularisation generalises best and whether ElasticNet
    consistently outperforms the pure penalties.
    """
    if save_dir is None:
        save_dir = RESULTS_DIR

    sns.set_theme(style="whitegrid", font_scale=1.1)
    palette = {"l1": "#E53935", "l2": "#1E88E5", "elasticnet": "#7B1FA2"}

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, (metric, ylabel) in zip(
        axes, [("f1_score", "Mean F1 Score"), ("pr_auc", "Mean PR-AUC")]
    ):
        agg = df.groupby(["dataset", "penalty"])[metric].mean().reset_index()
        sns.barplot(
            data=agg, x="dataset", y=metric, hue="penalty",
            palette=palette, ax=ax, edgecolor="black", linewidth=0.5,
        )
        ax.set_title(f"L1 vs L2 vs ElasticNet -- {ylabel}", fontsize=13)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xlabel("Dataset", fontsize=11)
        ax.set_ylim([0, 1.15])
        ax.legend(title="Regularisation", fontsize=9)

    # Add a delta table below as a text annotation
    fig.suptitle(
        "Q2/Q3: Which Regularisation Generalises Best?\n"
        "Does ElasticNet Consistently Outperform L1 and L2?",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "analysis_q2q3_regularization_comparison.png", save_dir)


# ── Q4: Imbalance handling comparison ────────────────────────────────────────

def plot_imbalance_comparison(df: pd.DataFrame, save_dir: str | None = None) -> None:
    """
    Q4: SMOTE vs UnderSample vs ClassWeight -- interaction with regularisation.

    Left panel: per-dataset F1.
    Right panel: precision-recall tradeoff (PR-AUC) per strategy.
    """
    if save_dir is None:
        save_dir = RESULTS_DIR

    sns.set_theme(style="whitegrid", font_scale=1.1)
    all_palette = {"SMOTE": "#43A047", "ClassWeight": "#FB8C00", "UnderSample": "#E53935"}
    available   = df["imbalance_strategy"].unique()
    palette     = {k: v for k, v in all_palette.items() if k in available}

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, (metric, ylabel) in zip(
        axes, [("f1_score", "Mean F1 Score"), ("pr_auc", "Mean PR-AUC")]
    ):
        agg = df.groupby(["dataset", "imbalance_strategy"])[metric].mean().reset_index()
        sns.barplot(
            data=agg, x="dataset", y=metric, hue="imbalance_strategy",
            palette=palette, ax=ax, edgecolor="black", linewidth=0.5,
        )
        _label_bars(ax)
        ax.set_title(f"Imbalance Strategy -- {ylabel}", fontsize=13)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xlabel("Dataset", fontsize=11)
        ax.set_ylim([0, 1.15])
        ax.legend(title="Strategy", fontsize=9)

    fig.suptitle(
        "Q4: How Does Imbalance Handling Interact with Regularisation?\n"
        "Precision-Recall tradeoff: SMOTE (oversampling) vs UnderSample vs ClassWeight",
        fontsize=13, fontweight="bold",
    )
    plt.tight_layout()
    _save(fig, "analysis_q4_imbalance_comparison.png", save_dir)


# ── Precision vs Recall tradeoff per strategy ─────────────────────────────────

def plot_precision_recall_tradeoff(df: pd.DataFrame, save_dir: str | None = None) -> None:
    """
    Scatter: mean Precision (proxy via PR-AUC) vs mean Recall (proxy via F1),
    coloured by imbalance strategy. Visualises the precision-recall tradeoff
    required by Requirement 6.
    """
    if save_dir is None:
        save_dir = RESULTS_DIR

    # Derive proxy precision and recall from stored metrics
    # F1 = 2*P*R/(P+R), PR-AUC integrates the whole curve.
    # We use F1 on x-axis and PR-AUC on y-axis to show strategy effect.
    sns.set_theme(style="whitegrid", font_scale=1.1)
    all_palette = {"SMOTE": "#43A047", "ClassWeight": "#FB8C00", "UnderSample": "#E53935"}
    available   = df["imbalance_strategy"].unique()
    palette     = {k: v for k, v in all_palette.items() if k in available}

    fig, ax = plt.subplots(figsize=(9, 7))

    for strategy in available:
        sub = df[df["imbalance_strategy"] == strategy]
        ax.scatter(
            sub["f1_score"], sub["pr_auc"],
            label=strategy, color=palette.get(strategy, "grey"),
            alpha=0.7, s=60, edgecolors="black", linewidth=0.4,
        )

    ax.set_xlabel("F1 Score (harmonic mean of Precision & Recall)", fontsize=12)
    ax.set_ylabel("PR-AUC (area under Precision-Recall curve)", fontsize=12)
    ax.set_title(
        "Precision-Recall Tradeoff by Imbalance Strategy\n"
        "Upper-right corner = best (high precision AND high recall)",
        fontsize=13,
    )
    ax.legend(title="Strategy", fontsize=10)
    ax.set_xlim([-0.05, 1.05])
    ax.set_ylim([-0.05, 1.05])

    _save(fig, "analysis_precision_recall_tradeoff.png", save_dir)


# ── Summary heatmap ───────────────────────────────────────────────────────────

def plot_summary_heatmap(df: pd.DataFrame, save_dir: str | None = None) -> None:
    """
    Heatmap of mean F1 scores across all experiment dimensions.
    Rows: dataset x pipeline. Columns: penalty x imbalance strategy.
    Provides a single-glance comparative view of all 36 configurations.
    """
    if save_dir is None:
        save_dir = RESULTS_DIR

    sns.set_theme(style="white", font_scale=0.95)

    df_c = df.copy()
    df_c["col"] = df_c["penalty"] + "\n" + df_c["imbalance_strategy"]
    df_c["row"] = df_c["dataset"] + "\n" + df_c["pipeline"]

    pivot = df_c.pivot_table(
        values="f1_score", index="row", columns="col", aggfunc="mean"
    )

    n_rows, n_cols = pivot.shape
    fig, ax = plt.subplots(figsize=(max(12, n_cols * 1.6), max(4, n_rows * 1.2)))
    sns.heatmap(
        pivot, annot=True, fmt=".3f", cmap="RdYlGn",
        vmin=0, vmax=1, ax=ax, linewidths=0.5,
        cbar_kws={"label": "F1 Score"},
    )
    ax.set_title(
        "F1 Score Heatmap -- All Configurations\n"
        "(Dataset x Pipeline)  vs  (Regularisation x Imbalance Strategy)",
        fontsize=13, fontweight="bold",
    )
    ax.set_xlabel("Regularisation | Imbalance Strategy", fontsize=11)
    ax.set_ylabel("Dataset | Pipeline", fontsize=11)
    plt.xticks(rotation=30, ha="right", fontsize=9)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    _save(fig, "analysis_summary_heatmap.png", save_dir)


# ── Underfitting / Overfitting scenario table plot ────────────────────────────

def plot_overfit_underfit_scenarios(rows: list[dict], save_dir: str | None = None) -> None:
    """
    Bar chart comparing train vs val F1 across explicit
    Underfitting / Normal / Overfitting scenarios (Requirement 4).
    """
    if save_dir is None:
        save_dir = RESULTS_DIR

    if not rows:
        return

    df = pd.DataFrame(rows)
    x  = np.arange(len(df))
    w  = 0.35

    sns.set_theme(style="whitegrid", font_scale=1.1)
    fig, ax = plt.subplots(figsize=(10, 6))

    bars_tr  = ax.bar(x - w / 2, df["train_f1"], w, label="Train F1",
                      color="#E53935", alpha=0.8, edgecolor="black", linewidth=0.5)
    bars_val = ax.bar(x + w / 2, df["val_f1"],   w, label="Validation F1",
                      color="#1E88E5", alpha=0.8, edgecolor="black", linewidth=0.5)

    for bar in list(bars_tr) + list(bars_val):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.01,
                f"{h:.3f}", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(df["scenario"], fontsize=10)
    ax.set_ylabel("F1 Score", fontsize=12)
    ax.set_ylim([0, 1.15])
    ax.set_title(
        "Overfitting & Underfitting Scenarios (UCI Dataset)\n"
        "Train vs Validation F1 -- gap shows generalisation failure",
        fontsize=13,
    )
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    _save(fig, "analysis_overfit_underfit_scenarios.png", save_dir)
