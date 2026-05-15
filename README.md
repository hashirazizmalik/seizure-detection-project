# Epileptic Seizure Detection — End-to-End ML Pipeline

A complete machine learning study using **Logistic Regression** to detect epileptic seizures
from EEG data, covering preprocessing pipelines, regularisation, class imbalance handling,
and comparative analysis. Includes an IEEE-format research paper.

---

## Project Structure

```
seizure-detection-project/
├── src/
│   ├── download_data.py    # Downloads all 3 datasets
│   ├── data_loader.py      # Parses datasets → (X, y) arrays
│   ├── pipelines.py        # Pipeline A and Pipeline B definitions
│   ├── trainer.py          # Logistic Regression + SMOTE/Undersample
│   ├── evaluation.py       # Metrics, PR curves, learning curves, sparsity
│   └── analysis.py         # Comparative analysis plots (Q1–Q4)
├── main.py                 # Full experiment orchestrator (5 phases)
├── generate_paper.py       # Generates IEEE Word document
├── requirements.txt
└── README.md
```

---

## Quickstart

### 1. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download datasets

```bash
python src/download_data.py
```

This downloads:
- **UCI Epileptic Seizure Recognition** — via GitHub mirror (~7 MB)
- **CHB-MIT EDF subset** — 3 files from PhysioNet (~121 MB, takes ~15 min)
- **Kaggle iEEG** — requires Kaggle API key (see below), otherwise skipped gracefully

#### Optional: Kaggle dataset setup

```bash
# 1. Create a Kaggle account at kaggle.com
# 2. Go to Account → API → Create New Token  → downloads kaggle.json
# 3. Place it at:
mkdir -p ~/.kaggle
cp kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
# 4. Accept competition rules at kaggle.com/c/seizure-detection
# 5. Re-run: python src/download_data.py
```

### 4. Run the full ML pipeline

```bash
python main.py
```

**Runtime:** ~25–30 minutes (CHB-MIT EDF parsing + learning curves are slow).

Output is written to `results/`:
- `comparison_results.csv` — 36 experiment rows (Accuracy, F1, PR-AUC)
- `pr_curve_*.png` — 36 precision-recall curve plots
- `reg_path_*.png` — regularisation path (underfitting/overfitting)
- `learning_curve_*.png` — learning curves
- `sparsity_*.png` — coefficient sparsity analysis
- `analysis_q1_*.png` — pipeline comparison
- `analysis_q2q3_*.png` — regularisation comparison
- `analysis_q4_*.png` — imbalance handling comparison
- `analysis_summary_heatmap.png` — F1 heatmap across all 36 configurations

### 5. Generate the research paper

```bash
python generate_paper.py
```

Output: `research_paper/Seizure_Detection_Research_Paper.docx` (IEEE format)

---

## What the Pipeline Does

### Phase 1 — Full Experiment Grid (36 configurations)

| Axis | Options |
|---|---|
| Datasets | UCI, CHB-MIT (Kaggle skipped if no API key) |
| Pipelines | Pipeline A (normalise → bandpass → SelectKBest), Pipeline B (stat features → scale → PCA) |
| Regularisation | L1 (Lasso), L2 (Ridge), ElasticNet |
| Imbalance handling | SMOTE, Random Undersampling, Class Weighting |

### Phase 2 — Overfitting & Underfitting Demo
- Regularisation path: C sweep from 10⁻⁴ to 10³
- Explicit scenarios: C=0.001 (underfit), C=1.0 (normal), C=1000 (overfit)

### Phase 3 — Learning Curves
- Pipeline B + L2, 5-fold stratified CV, training size 50–100%

### Phase 4 — Sparsity Analysis
- L1 vs ElasticNet vs L2 coefficient magnitudes on all 178 UCI features

### Phase 5 — Comparative Analysis
- Q1: Does preprocessing order affect results?
- Q2/Q3: Which regularisation generalises best? Does ElasticNet outperform?
- Q4: How does imbalance handling interact with regularisation?

---

## Key Results

| Configuration | Accuracy | F1 | PR-AUC |
|---|---|---|---|
| **UCI + Pipeline B + L2 + SMOTE** | 0.957 | **0.899** | **0.964** |
| UCI + Pipeline A + L2 + SMOTE | 0.682 | 0.375 | 0.472 |
| CHB-MIT + Pipeline B + L1 + UnderSample | 0.969 | 0.190 | **0.625** |
| CHB-MIT + Pipeline A + any | ~0.97 | ~0.000 | ~0.005 |

**Sparsity:** L1 uses 46/178 features (74% sparse). L2 uses all 178.

---

## Datasets

| Dataset | Samples | Features | Imbalance | Type |
|---|---|---|---|---|
| UCI Epileptic Seizure | 11,500 | 178 | 4:1 | Time-series EEG |
| CHB-MIT (3 files) | 5,400 | 11,776 | 270:1 | Raw multichannel EEG |
| Kaggle iEEG | — | — | ~10:1 | Intracranial EEG (.mat) |

---

## Requirements

- Python ≥ 3.10
- scikit-learn ≥ 1.8.0 (uses `l1_ratio` API — older versions not supported)
- See `requirements.txt` for full pinned versions

---

## Notes

- The CHB-MIT download takes ~15 minutes on a typical connection (3 × 40 MB EDF files from PhysioNet).
- All experiments are fully reproducible with `RANDOM_STATE=42`.
- The `venv/`, `data/raw/chbmit/*.edf`, and `results/` directories are git-ignored.
- The UCI CSV and CHB-MIT summary file are small enough to commit if desired.
