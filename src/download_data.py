"""
download_data.py — Storage-Optimized Dataset Downloader

Downloads lightweight subsets of 3 EEG seizure datasets:
  1. UCI Epileptic Seizure Recognition (via ucimlrepo, fallback to direct URL)
  2. CHB-MIT subset (3 EDF files via urllib from PhysioNet, with retries)
  3. Kaggle iEEG Dog_1 subset (via kaggle CLI)

All downloads are idempotent — existing files are skipped.
"""

import os
import time
import subprocess
import urllib.request
import zipfile
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
UCI_DIR = os.path.join(RAW_DIR, "uci")
CHBMIT_DIR = os.path.join(RAW_DIR, "chbmit")
KAGGLE_DIR = os.path.join(RAW_DIR, "kaggle")


# ── 1. UCI Epileptic Seizure Recognition ──────────────────────────────────────
UCI_RAW_URL = (
    "https://raw.githubusercontent.com/akshayg056/"
    "Epileptic-seizure-detection-/master/data.csv"
)


def download_uci(dest_dir: str = UCI_DIR) -> None:
    """Download UCI Epileptic Seizure dataset from GitHub mirror."""
    csv_path = os.path.join(dest_dir, "epileptic_seizure.csv")
    if os.path.exists(csv_path):
        logger.info("UCI dataset already exists at %s — skipping.", csv_path)
        return

    os.makedirs(dest_dir, exist_ok=True)
    logger.info("Downloading UCI dataset from GitHub mirror...")
    try:
        _download_with_retry(UCI_RAW_URL, csv_path, max_retries=3)
        logger.info("UCI dataset saved to %s.", csv_path)
    except Exception as exc:
        logger.error("UCI download failed: %s", exc)
        raise



# ── 2. CHB-MIT (PhysioNet) — 3 EDF files only ────────────────────────────────
CHBMIT_BASE_URL = "https://physionet.org/files/chbmit/1.0.0/chb01/"
CHBMIT_FILES = ["chb01_01.edf", "chb01_02.edf", "chb01_03.edf"]
CHBMIT_SUMMARY = "chb01-summary.txt"


def download_chbmit(dest_dir: str = CHBMIT_DIR) -> None:
    """Download 3 EDF files + summary from CHB-MIT on PhysioNet (with retries)."""
    os.makedirs(dest_dir, exist_ok=True)

    files_to_get = CHBMIT_FILES + [CHBMIT_SUMMARY]
    for filename in files_to_get:
        filepath = os.path.join(dest_dir, filename)

        # Check if file exists AND is complete (not a partial download)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            logger.info("%s already exists (%.1f MB) — skipping.",
                        filename, os.path.getsize(filepath) / (1024 * 1024))
            continue

        # Remove partial downloads
        if os.path.exists(filepath):
            os.remove(filepath)

        url = CHBMIT_BASE_URL + filename
        logger.info("Downloading %s ...", url)
        _download_with_retry(url, filepath, max_retries=3)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info("Saved %s (%.1f MB).", filename, size_mb)


# ── 3. Kaggle iEEG — Dog_1.zip only ──────────────────────────────────────────
def download_kaggle(dest_dir: str = KAGGLE_DIR) -> None:
    """Download Dog_1.zip from Kaggle seizure-detection competition."""
    os.makedirs(dest_dir, exist_ok=True)
    zip_path = os.path.join(dest_dir, "Dog_1.zip")
    extracted_marker = os.path.join(dest_dir, "Dog_1")

    if os.path.exists(extracted_marker):
        logger.info("Kaggle Dog_1 already extracted — skipping.")
        return

    if not os.path.exists(zip_path):
        logger.info("Downloading Dog_1.zip via Kaggle CLI...")
        try:
            subprocess.run(
                [
                    "kaggle", "competitions", "download",
                    "-c", "seizure-detection",
                    "-f", "Dog_1.zip",
                    "-p", dest_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Dog_1.zip downloaded to %s.", dest_dir)
        except FileNotFoundError:
            logger.warning(
                "Kaggle CLI not found. Install with: pip install kaggle\n"
                "Then configure ~/.kaggle/kaggle.json with your API key."
            )
            return
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "Kaggle download failed (auth issue?): %s\n"
                "Ensure ~/.kaggle/kaggle.json exists and you've accepted "
                "competition rules at kaggle.com/c/seizure-detection.",
                exc.stderr.strip(),
            )
            return

    # Extract
    logger.info("Extracting Dog_1.zip...")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        logger.info("Extracted to %s.", dest_dir)
        os.remove(zip_path)
        logger.info("Removed %s to save storage.", zip_path)
    except Exception as exc:
        logger.error("Extraction failed: %s", exc)
        raise


# ── Utilities ─────────────────────────────────────────────────────────────────
def _download_with_retry(url: str, filepath: str, max_retries: int = 3) -> None:
    """Download a file with retry logic for unreliable connections."""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("  Attempt %d/%d: %s", attempt, max_retries, url)
            urllib.request.urlretrieve(url, filepath)
            return
        except Exception as exc:
            if attempt < max_retries:
                wait = 5 * attempt
                logger.warning("  Failed (attempt %d): %s. Retrying in %ds...",
                               attempt, exc, wait)
                # Remove partial file
                if os.path.exists(filepath):
                    os.remove(filepath)
                time.sleep(wait)
            else:
                logger.error("  All %d attempts failed for %s", max_retries, url)
                raise


# ── Main ──────────────────────────────────────────────────────────────────────
def download_all() -> None:
    """Download all datasets. Failures are logged but don't halt execution."""
    logger.info("=" * 60)
    logger.info("SEIZURE DETECTION — Dataset Downloader (LITE)")
    logger.info("=" * 60)

    for name, func in [
        ("UCI", download_uci),
        ("CHB-MIT", download_chbmit),
        ("Kaggle", download_kaggle),
    ]:
        try:
            logger.info("── %s ──", name)
            func()
        except Exception as exc:
            logger.error("Could not download %s dataset: %s", name, exc)
            logger.info("Continuing with remaining datasets...")

    logger.info("=" * 60)
    logger.info("Download phase complete.")
    logger.info("=" * 60)


if __name__ == "__main__":
    download_all()
