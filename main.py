"""
main.py -- Anti-Gravity Execution Engine

Fulfils all 7 assignment requirements:

  Req 1  Dataset Collection      -- UCI (11500 samples, 4:1 imbalance, time-series)
                                     CHB-MIT (5400 windows, 270:1 imbalance, raw EEG)
                                     Kaggle (skipped gracefully -- needs API key)

  Req 2  Preprocessing Pipelines -- Pipeline A: Normalise -> BandpassFilter -> SelectKBest
                                     Pipeline B: StatFeatures -> StandardScaler -> PCA

  Req 3  Logistic Regression      -- Accuracy, F1-score, PR-AUC reported

  Req 4  Overfit / Underfit       -- Phase 2: regularisation path (C sweep)
                                     Phase 3: learning curves (train vs CV vs set size)
                                     Explicit scenario table: C=0.001/1.0/1000

  Req 5  Regularisation Study     -- L1, L2, ElasticNet compared on all datasets
                                     Phase 4: sparsity analysis (coefficient magnitudes)

  Req 6  Class Imbalance          -- SMOTE, UnderSampling, ClassWeighting compared

  Req 7  Comparative Analysis     -- Phase 5: Q1-Q4 bar charts + summary heatmap
"""

import logging
import warnings
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.exceptions import ConvergenceWarning
from sklearn.pipeline import Pipeline as SKPipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.decomposition import PCA

from src.data_loader import DATASET_LOADERS
from src.pipelines import PIPELINE_BUILDERS, BandpassFilter, StatisticalFeatureExtractor
from src.trainer import train_model
from src.evaluation import (
    evaluate_model,
    save_results_csv,
    plot_learning_curves,
    plot_regularization_path,
    plot_sparsity_analysis,
)
from src.analysis import (
    plot_pipeline_comparison,
    plot_regularization_comparison,
    plot_imbalance_comparison,
    plot_precision_recall_tradeoff,
    plot_summary_heatmap,
    plot_overfit_underfit_scenarios,
)

# ── Logging & warning suppression ────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=ConvergenceWarning)

# ── Experiment grid constants ─────────────────────────────────────────────────
PENALTIES = ["l1", "l2", "elasticnet"]

IMBALANCE_STRATEGIES = {
    "SMOTE":       {"use_smote": True,  "class_weight": None,       "use_undersample": False},
    "ClassWeight": {"use_smote": False, "class_weight": "balanced", "use_undersample": False},
    "UnderSample": {"use_smote": False, "class_weight": None,       "use_undersample": True},
}

TEST_SIZE    = 0.2
RANDOM_STATE = 42


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 -- Full experiment grid
# ─────────────────────────────────────────────────────────────────────────────

def run_experiment(
    dataset_name: str,
    X: np.ndarray,
    y: np.ndarray,
    pipeline_name: str,
    penalty: str,
    strategy_name: str,
    strategy_params: dict,
) -> dict | None:
    """Run one experiment configuration. Returns result dict or None on failure."""
    label = f"{dataset_name}_{pipeline_name}_{penalty}_{strategy_name}"
    logger.info("-- %s", label)

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
        )

        pipeline = PIPELINE_BUILDERS[pipeline_name]()
        if pipeline_name == "Pipeline_A":
            pipeline.set_params(feature_select__k=min(50, X_train.shape[1]))
        if pipeline_name == "Pipeline_B":
            pipeline.set_params(pca__n_components=min(8, 9))

        X_train_t = pipeline.fit_transform(X_train, y_train)
        X_test_t  = pipeline.transform(X_test)

        model  = train_model(X_train_t, y_train, penalty=penalty, **strategy_params)
        y_pred  = model.predict(X_test_t)
        y_proba = model.predict_proba(X_test_t)[:, 1]

        result = evaluate_model(y_test, y_pred, y_proba, label=label)
        result.update({
            "dataset":            dataset_name,
            "pipeline":           pipeline_name,
            "penalty":            penalty,
            "imbalance_strategy": strategy_name,
        })
        return result

    except Exception as exc:
        logger.error("FAILED %s: %s", label, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 -- Overfitting & Underfitting (Requirement 4)
# ─────────────────────────────────────────────────────────────────────────────

def demo_regularization_path(X: np.ndarray, y: np.ndarray, dataset_name: str) -> list[dict]:
    """
    Two outputs:
      (a) Continuous C-sweep plot: train vs val F1 showing under/overfitting zones.
      (b) Three explicit scenarios (C=0.001/1.0/1000) with a bar chart.
    """
    logger.info("=" * 60)
    logger.info("PHASE 2: Regularisation Path -- %s", dataset_name)
    logger.info("=" * 60)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
    )

    # (a) Continuous C sweep on Pipeline_A features (50 features)
    pipe_a = PIPELINE_BUILDERS["Pipeline_A"]()
    pipe_a.set_params(feature_select__k=min(50, X_train.shape[1]))
    Xtr_a = pipe_a.fit_transform(X_train, y_train)
    Xte_a = pipe_a.transform(X_test)

    plot_regularization_path(Xtr_a, Xte_a, y_train, y_test,
                             label=f"{dataset_name}_Pipeline_A_50feat")

    # (b) Explicit underfitting / normal / overfitting scenarios
    scenarios = [
        # (display name,      C,      k_features)
        ("Underfitting\nC=0.001, k=5",   0.001,  5),
        ("Normal\nC=1.0, k=50",          1.0,    50),
        ("Overfitting\nC=1000, k=all",   1000.0, X_train.shape[1]),
    ]

    rows = []
    for scenario_name, C, k in scenarios:
        p = PIPELINE_BUILDERS["Pipeline_A"]()
        p.set_params(feature_select__k=min(k, X_train.shape[1]))
        Xtr = p.fit_transform(X_train, y_train)
        Xte = p.transform(X_test)

        model    = LogisticRegression(C=C, l1_ratio=0.0, solver="saga",
                                      max_iter=3000, random_state=RANDOM_STATE)
        model.fit(Xtr, y_train)
        train_f1 = f1_score(y_train, model.predict(Xtr), zero_division=0)
        val_f1   = f1_score(y_test,  model.predict(Xte), zero_division=0)

        logger.info("  %-30s | Train F1=%.4f | Val F1=%.4f | Gap=%.4f",
                    scenario_name.replace("\n", " "), train_f1, val_f1, train_f1 - val_f1)
        rows.append({
            "scenario": scenario_name,
            "C":        C,
            "k":        k,
            "train_f1": train_f1,
            "val_f1":   val_f1,
            "gap":      train_f1 - val_f1,
        })

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 -- Learning curves (Requirement 4)
# ─────────────────────────────────────────────────────────────────────────────

def demo_learning_curves(X: np.ndarray, y: np.ndarray, dataset_name: str) -> None:
    """
    Learning curves for Pipeline B + L2 on the given dataset.
    Shows how model accuracy scales with training data volume.
    A persistent train-val gap at maximum data -> overfitting.
    """
    logger.info("=" * 60)
    logger.info("PHASE 3: Learning Curves -- %s", dataset_name)
    logger.info("=" * 60)

    n_pca = min(8, X.shape[1], 9)
    estimator = SKPipeline([
        ("extract", StatisticalFeatureExtractor()),
        ("scale",   StandardScaler()),
        ("pca",     PCA(n_components=n_pca)),
        ("lr",      LogisticRegression(
            C=1.0, l1_ratio=0.0, solver="saga",
            max_iter=2000, random_state=RANDOM_STATE,
        )),
    ])
    plot_learning_curves(estimator, X, y, label=f"{dataset_name}_Pipeline_B_L2")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 -- Sparsity analysis (Requirement 5)
# ─────────────────────────────────────────────────────────────────────────────

def demo_sparsity_analysis(X: np.ndarray, y: np.ndarray, dataset_name: str) -> None:
    """
    Analyse L1 / ElasticNet / L2 coefficient sparsity on normalised + denoised
    features (MinMaxScaler + BandpassFilter, all 178 features).

    Demonstrates L1's implicit feature selection vs L2's dense solution.
    """
    logger.info("=" * 60)
    logger.info("PHASE 4: Sparsity Analysis -- %s", dataset_name)
    logger.info("=" * 60)

    X_train, _, y_train, _ = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y,
    )
    # Preprocess with MinMaxScaler + BandpassFilter but NO SelectKBest
    # so all features feed into the regularised LR model.
    prep = SKPipeline([
        ("normalize", MinMaxScaler()),
        ("denoise",   BandpassFilter()),
    ])
    X_tr = prep.fit_transform(X_train)
    plot_sparsity_analysis(X_tr, y_train, label=f"{dataset_name}_all_features")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 -- Comparative analysis (Requirement 7)
# ─────────────────────────────────────────────────────────────────────────────

def run_comparative_analysis(all_results: list[dict], overfit_rows: list[dict]) -> None:
    """Generate all Q1-Q4 comparison plots plus the summary heatmap."""
    logger.info("=" * 60)
    logger.info("PHASE 5: Comparative Analysis")
    logger.info("=" * 60)

    df = pd.DataFrame(all_results)

    plot_pipeline_comparison(df)
    plot_regularization_comparison(df)
    plot_imbalance_comparison(df)
    plot_precision_recall_tradeoff(df)
    plot_summary_heatmap(df)
    plot_overfit_underfit_scenarios(overfit_rows)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 60)
    logger.info("SEIZURE DETECTION -- Anti-Gravity Pipeline (LITE)")
    logger.info("=" * 60)

    loaded_datasets: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    all_results:     list[dict] = []

    # ── Phase 1: Full experiment grid ─────────────────────────────────────────
    logger.info("\n%s\nPHASE 1: Full Experiment Grid\n%s", "=" * 60, "=" * 60)

    for ds_name, loader_fn in DATASET_LOADERS.items():
        logger.info("\nLoading dataset: %s", ds_name)
        try:
            X, y = loader_fn()
        except Exception as exc:
            logger.error("Could not load %s: %s -- skipping.", ds_name, exc)
            continue

        unique, counts = np.unique(y, return_counts=True)
        if len(unique) < 2:
            logger.error("%s has only 1 class -- skipping.", ds_name)
            continue
        if min(counts) < 5:
            logger.warning("%s minority class = %d samples.", ds_name, min(counts))

        loaded_datasets[ds_name] = (X, y)

        for pipe_name in PIPELINE_BUILDERS:
            for penalty in PENALTIES:
                for strat_name, strat_params in IMBALANCE_STRATEGIES.items():
                    result = run_experiment(
                        ds_name, X, y,
                        pipe_name, penalty,
                        strat_name, strat_params,
                    )
                    if result is not None:
                        all_results.append(result)

    # ── Phase 2: Regularisation path / overfit-underfit demo ─────────────────
    overfit_rows: list[dict] = []
    if "UCI" in loaded_datasets:
        overfit_rows = demo_regularization_path(*loaded_datasets["UCI"], "UCI")

    # ── Phase 3: Learning curves ──────────────────────────────────────────────
    if "UCI" in loaded_datasets:
        demo_learning_curves(*loaded_datasets["UCI"], "UCI")
    # CHB-MIT skipped: only 20 minority samples, too few for stable CV folds

    # ── Phase 4: Sparsity analysis ────────────────────────────────────────────
    if "UCI" in loaded_datasets:
        demo_sparsity_analysis(*loaded_datasets["UCI"], "UCI")

    # ── Phase 5: Comparative analysis ────────────────────────────────────────
    if all_results:
        csv_path = save_results_csv(all_results)
        run_comparative_analysis(all_results, overfit_rows)

        df = pd.DataFrame(all_results)

        logger.info("\n%s", "=" * 60)
        logger.info("DONE -- %d experiments completed.", len(all_results))
        logger.info("CSV    : %s", csv_path)
        logger.info("Plots  : results/*.png")
        logger.info("%s", "=" * 60)

        cols = ["dataset", "pipeline", "penalty", "imbalance_strategy",
                "accuracy", "f1_score", "pr_auc"]
        print("\n" + df[cols].to_string(index=False))
    else:
        logger.error("No experiments completed.")


if __name__ == "__main__":
    main()
