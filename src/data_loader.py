"""
data_loader.py — Standardized Data Ingestion

Parses the 3 downloaded datasets into uniform (X, y) numpy arrays:
  - UCI:    CSV-based, 178 features per sample, 5-class → binarized
  - CHB-MIT: EDF files, windowed EEG segments, labeled via summary file
  - Kaggle: .mat files from Dog_1, preictal vs interictal
"""

import os
import re
import glob
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")


# ── 1. UCI Epileptic Seizure Recognition ──────────────────────────────────────
def load_uci_data() -> tuple[np.ndarray, np.ndarray]:
    """
    Load the UCI Epileptic Seizure Recognition dataset.

    Labels are binarized:
        y == 1  →  1 (Seizure)
        y ∈ {2,3,4,5}  →  0 (Non-Seizure)

    Returns:
        X: (n_samples, 178) float64 array
        y: (n_samples,) int array {0, 1}
    """
    csv_path = os.path.join(RAW_DIR, "uci", "epileptic_seizure.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"UCI dataset not found at {csv_path}. "
            "Run `python src/download_data.py` first."
        )

    logger.info("Loading UCI dataset from %s ...", csv_path)
    df = pd.read_csv(csv_path)

    # Drop unnamed index column if present
    if "Unnamed" in df.columns[0]:
        df = df.drop(columns=[df.columns[0]])

    # Last column is the target (y)
    X = df.iloc[:, :-1].values.astype(np.float64)
    y_raw = df.iloc[:, -1].values

    # Binarize: 1 → Seizure (1), everything else → Non-Seizure (0)
    y = (y_raw == 1).astype(int)

    logger.info(
        "UCI loaded: X=%s, y=%s | Seizure=%d, Non-Seizure=%d",
        X.shape, y.shape, y.sum(), (y == 0).sum(),
    )
    return X, y


# ── 2. CHB-MIT (EDF files) ───────────────────────────────────────────────────
def _parse_chbmit_summary(summary_path: str) -> dict:
    """
    Parse chb01-summary.txt to extract seizure onset/offset times per file.

    Returns:
        dict mapping filename → list of (start_sec, end_sec) tuples
    """
    seizures = {}
    current_file = None

    with open(summary_path, "r") as f:
        for line in f:
            line = line.strip()
            # Match: File Name: chb01_03.edf
            match_file = re.match(r"File Name:\s*(\S+)", line)
            if match_file:
                current_file = match_file.group(1)
                if current_file not in seizures:
                    seizures[current_file] = []

            # Match: Seizure Start Time: 2996 seconds
            match_start = re.match(
                r"Seizure\s*\d*\s*Start Time:\s*(\d+)\s*seconds", line,
                re.IGNORECASE,
            )
            if match_start and current_file:
                start = int(match_start.group(1))

            match_end = re.match(
                r"Seizure\s*\d*\s*End Time:\s*(\d+)\s*seconds", line,
                re.IGNORECASE,
            )
            if match_end and current_file:
                end = int(match_end.group(1))
                seizures[current_file].append((start, end))

    return seizures


def load_chbmit_data(
    window_seconds: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Load CHB-MIT EDF files and segment into fixed-length windows.

    Each window is labeled:
        1 = contains seizure activity
        0 = non-seizure (interictal)

    Args:
        window_seconds: Length of each window in seconds.

    Returns:
        X: (n_windows, n_channels * samples_per_window) float64 array
        y: (n_windows,) int array {0, 1}
    """
    chbmit_dir = os.path.join(RAW_DIR, "chbmit")
    summary_path = os.path.join(chbmit_dir, "chb01-summary.txt")

    if not os.path.exists(summary_path):
        raise FileNotFoundError(
            f"CHB-MIT summary not found at {summary_path}. "
            "Run `python src/download_data.py` first."
        )

    try:
        import pyedflib
    except ImportError:
        raise ImportError(
            "pyedflib is required for CHB-MIT data. "
            "Install with: pip install pyedflib"
        )

    seizure_map = _parse_chbmit_summary(summary_path)
    edf_files = sorted(glob.glob(os.path.join(chbmit_dir, "chb01_*.edf")))

    if not edf_files:
        raise FileNotFoundError(
            f"No EDF files found in {chbmit_dir}. "
            "Run `python src/download_data.py` first."
        )

    all_windows = []
    all_labels = []

    for edf_path in edf_files:
        filename = os.path.basename(edf_path)
        logger.info("Processing %s ...", filename)

        reader = pyedflib.EdfReader(edf_path)
        n_channels = reader.signals_in_file
        fs = reader.getSampleFrequency(0)
        n_samples = reader.getNSamples()[0]

        # Read all channels
        signals = np.array(
            [reader.readSignal(i) for i in range(n_channels)]
        )  # (n_channels, n_samples)
        reader.close()

        # Window parameters
        window_size = int(fs * window_seconds)
        n_windows = n_samples // window_size

        # Get seizure intervals for this file
        file_seizures = seizure_map.get(filename, [])

        for w in range(n_windows):
            start_sample = w * window_size
            end_sample = start_sample + window_size
            window_data = signals[:, start_sample:end_sample].flatten()
            all_windows.append(window_data)

            # Determine label: does this window overlap with any seizure?
            window_start_sec = start_sample / fs
            window_end_sec = end_sample / fs
            is_seizure = any(
                window_start_sec < sz_end and window_end_sec > sz_start
                for sz_start, sz_end in file_seizures
            )
            all_labels.append(int(is_seizure))

    X = np.array(all_windows, dtype=np.float64)
    y = np.array(all_labels, dtype=int)

    logger.info(
        "CHB-MIT loaded: X=%s, y=%s | Seizure=%d, Non-Seizure=%d",
        X.shape, y.shape, y.sum(), (y == 0).sum(),
    )
    return X, y


# ── 3. Kaggle iEEG (Dog_1) ───────────────────────────────────────────────────
def load_kaggle_data() -> tuple[np.ndarray, np.ndarray]:
    """
    Load the Kaggle iEEG Dog_1 dataset (.mat files).

    Preictal segments → 1 (Seizure/pre-seizure)
    Interictal segments → 0 (Normal)

    Returns:
        X: (n_segments, flattened_features) float64 array
        y: (n_segments,) int array {0, 1}
    """
    kaggle_dir = os.path.join(RAW_DIR, "kaggle")
    dog1_dir = os.path.join(kaggle_dir, "Dog_1")

    # Also check if files are directly in kaggle_dir
    if not os.path.exists(dog1_dir):
        dog1_dir = kaggle_dir

    try:
        from scipy.io import loadmat
    except ImportError:
        raise ImportError(
            "scipy is required for Kaggle .mat files. "
            "Install with: pip install scipy"
        )

    interictal_files = sorted(
        glob.glob(os.path.join(dog1_dir, "**", "*interictal*segment*.mat"), recursive=True)
    )
    preictal_files = sorted(
        glob.glob(os.path.join(dog1_dir, "**", "*preictal*segment*.mat"), recursive=True)
    )

    if not interictal_files and not preictal_files:
        raise FileNotFoundError(
            f"No .mat files found in {dog1_dir}. "
            "Run `python src/download_data.py` first."
        )

    all_features = []
    all_labels = []

    def _extract_segment(mat_path: str) -> np.ndarray:
        """Extract and flatten EEG data from a .mat file."""
        mat = loadmat(mat_path, simplify_cells=True)
        # The data key varies; find it dynamically
        for key in mat:
            if not key.startswith("_"):
                segment = mat[key]
                if isinstance(segment, dict) and "data" in segment:
                    data = np.array(segment["data"], dtype=np.float64)
                    # Subsample to keep features manageable
                    # Take mean across time for each channel
                    return data.mean(axis=1)
        raise ValueError(f"Could not find data in {mat_path}")

    for mat_file in interictal_files:
        try:
            features = _extract_segment(mat_file)
            all_features.append(features)
            all_labels.append(0)
        except Exception as exc:
            logger.warning("Skipping %s: %s", mat_file, exc)

    for mat_file in preictal_files:
        try:
            features = _extract_segment(mat_file)
            all_features.append(features)
            all_labels.append(1)
        except Exception as exc:
            logger.warning("Skipping %s: %s", mat_file, exc)

    if not all_features:
        raise ValueError("No valid segments could be loaded from Kaggle data.")

    X = np.array(all_features, dtype=np.float64)
    y = np.array(all_labels, dtype=int)

    logger.info(
        "Kaggle loaded: X=%s, y=%s | Preictal=%d, Interictal=%d",
        X.shape, y.shape, y.sum(), (y == 0).sum(),
    )
    return X, y


# ── Convenience ───────────────────────────────────────────────────────────────
DATASET_LOADERS = {
    "UCI": load_uci_data,
    "CHB-MIT": load_chbmit_data,
    "Kaggle": load_kaggle_data,
}
