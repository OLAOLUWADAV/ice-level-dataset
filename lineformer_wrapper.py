"""
W5: LineFormer integration wrapper for the ICE LEVEL DATASET pipeline.

Slots LineFormer in as a drop-in replacement for the colour-segmentation +
component-selection block of curve_extractor.py.

Setup (run once)
────────────────
  conda create -n LineFormer python=3.8
  conda activate LineFormer
  bash install.sh                        # from LineFormer repo root
  # download iter_3000.pth from Google Drive:
  # https://drive.google.com/drive/folders/1K_zLZwgoUIAJtfjwfCU5Nv33k17R0O5T

Usage
─────
  # Standalone:
  python lineformer_wrapper.py 1848_01_Jan.jpg

  # Via eval_extractor.py:
  python eval_extractor.py --gold gold_set/ --extractor lineformer

  # In code:
  from lineformer_wrapper import extract_curve_lineformer
  result = extract_curve_lineformer(Path("1848_01_Jan.jpg"), year=1848, month=1)

Output
──────
  Same dict as curve_extractor.extract_curve():
    era, grid_py, grid_px, blue_pct, coverage, confidence,
    centerline: [[x, y_or_null], …]
  Plus:
    lf_instance_count: int   — number of instances LineFormer detected
    lf_instance_scores: list — confidence score per instance
    lf_selected_instance: int — index of the instance used as the main curve

Configuration
─────────────
  Set LINEFORMER_DIR, CKPT, CONFIG below to match your local installation.
  The wrapper auto-detects when LineFormer is not installed and raises a
  clear error rather than silently degrading.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

# ── Configuration — adjust to your local LineFormer installation ─────────────
LINEFORMER_DIR = Path.home() / "LineFormer"      # git clone destination
CKPT           = LINEFORMER_DIR / "iter_3000.pth"
CONFIG         = LINEFORMER_DIR / "lineformer_swin_t_config.py"
DEVICE         = "cpu"                           # "cuda:0" if GPU available
# ─────────────────────────────────────────────────────────────────────────────

_model_loaded = False


def _ensure_model() -> None:
    global _model_loaded
    if _model_loaded:
        return

    if not LINEFORMER_DIR.is_dir():
        raise RuntimeError(
            f"LineFormer not found at {LINEFORMER_DIR}.\n"
            "  Clone with: git clone https://github.com/TheJaeLal/LineFormer\n"
            "  Then: conda activate LineFormer && bash install.sh"
        )
    if not CKPT.exists():
        raise RuntimeError(
            f"Checkpoint not found: {CKPT}\n"
            "  Download iter_3000.pth from:\n"
            "  https://drive.google.com/drive/folders/1K_zLZwgoUIAJtfjwfCU5Nv33k17R0O5T"
        )

    # Add LineFormer to sys.path so its imports resolve
    lf_str = str(LINEFORMER_DIR)
    if lf_str not in sys.path:
        sys.path.insert(0, lf_str)

    import infer
    infer.load_model(str(CONFIG), str(CKPT), DEVICE)
    _model_loaded = True


def _score_instance(keypoints: "np.ndarray", H: int, W: int) -> float:
    """
    Re-use the same heuristic scoring from curve_extractor.select_curve_component:
    x-coverage × 0.5 + continuity × 0.3 + position_prior × 0.1 + size × 0.1.
    """
    import numpy as np

    if keypoints is None or len(keypoints) == 0:
        return 0.0

    xs = keypoints[:, 0].astype(int)
    ys = keypoints[:, 1].astype(float)
    unique_xs = np.unique(xs)

    # x-coverage
    cov = len(unique_xs) / W

    # continuity (fraction of x-cols with a neighbour within 3)
    xs_set = set(unique_xs.tolist())
    cont = sum(1 for x in xs_set
               if (x-1) in xs_set or (x+1) in xs_set
               or (x-2) in xs_set or (x+2) in xs_set) / max(len(xs_set), 1)

    # position prior (centroid in lower 70%)
    cy = float(ys.mean()) / H
    pos = max(0.0, cy / 0.3) if cy < 0.3 else 1.0

    # size
    size_norm = min(len(keypoints) / (W * H * 0.02), 1.0)

    return cov * 0.5 + cont * 0.3 + pos * 0.1 + size_norm * 0.1


def _instance_to_centerline(
    keypoints: "np.ndarray",
    W: int,
    H: int,
) -> tuple[list[list], float]:
    """
    Convert LineFormer keypoints (N×2 array of x,y) to our
    centerline format: [[x, y_or_null], …] for x in range(W).
    Groups by x-column, takes the mean y per column, median-smooths.
    """
    import numpy as np

    col_ys: dict[int, list[float]] = {}
    for x, y in keypoints:
        xi = int(round(x))
        if 0 <= xi < W:
            col_ys.setdefault(xi, []).append(float(y))

    raw = np.full(W, np.nan)
    for xi, ys in col_ys.items():
        raw[xi] = float(np.mean(ys))

    # 7-column median smoothing (same as curve_extractor)
    smoothed = raw.copy()
    win = 7
    for i in range(W):
        lo = max(0, i - win // 2)
        hi = min(W, i + win // 2 + 1)
        seg = raw[lo:hi]
        seg = seg[~np.isnan(seg)]
        if seg.size > 0:
            smoothed[i] = float(np.median(seg))

    present = int((~np.isnan(smoothed)).sum())
    centerline = [
        [x, None if np.isnan(smoothed[x]) else round(float(smoothed[x]), 1)]
        for x in range(W)
    ]
    coverage = present / W
    return centerline, coverage


def extract_curve_lineformer(
    tile_path: Path,
    *,
    year: int | None = None,
    month: int | None = None,
    to_clean: bool = False,
) -> dict:
    """
    Full LineFormer extraction for a single tile.

    Parameters
    ----------
    tile_path : path to a 744×3000 JPEG tile
    year, month : calendar assignment (from filename if None)
    to_clean   : pass to LineFormer's to_clean parameter (runs clean_chart.py)

    Returns
    -------
    Same shape as curve_extractor.extract_curve():
      era, grid_py, grid_px, blue_pct, coverage, confidence, centerline
    Plus LineFormer-specific fields:
      lf_instance_count, lf_instance_scores, lf_selected_instance
    """
    import cv2
    import re as _re
    import numpy as np

    _ensure_model()
    import infer
    import line_utils
    from curve_extractor import (
        _load_rgb, _to_gray,
        detect_grid_spacing, classify_era, measure_blue_pct,
    )

    tile_path = Path(tile_path)

    # Parse year/month from filename if not provided
    if year is None or month is None:
        m = _re.match(r"(\d{4})_(\d{2})", tile_path.name)
        if m:
            year  = int(m.group(1))
            month = int(m.group(2))

    # Load image — LineFormer expects BGR (OpenCV convention)
    img_bgr = cv2.imread(str(tile_path))
    if img_bgr is None:
        raise FileNotFoundError(f"Cannot open tile: {tile_path}")
    H, W = img_bgr.shape[:2]

    # Keep our era detection (it doesn't require colour segmentation)
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    gray = _to_gray(rgb)
    grid_py, grid_px = detect_grid_spacing(gray)
    blue_pct = measure_blue_pct(rgb)
    era = classify_era(grid_py, blue_pct)

    # Run LineFormer
    line_dataseries = infer.get_dataseries(img_bgr, to_clean=to_clean)
    instances = line_utils.points_to_array(line_dataseries)   # list of N×2 arrays

    if not instances:
        return {
            "file": tile_path.name,
            "year": year, "month": month,
            "era": era, "grid_py": round(grid_py, 1), "grid_px": round(grid_px, 1),
            "blue_pct": round(blue_pct, 4),
            "coverage": 0.0, "confidence": 0.0,
            "centerline": [[x, None] for x in range(W)],
            "lf_instance_count": 0,
            "lf_instance_scores": [],
            "lf_selected_instance": None,
        }

    # Score each instance with our heuristic; pick best
    scores = [_score_instance(inst, H, W) for inst in instances]
    best_idx = int(np.argmax(scores))
    best_kps = instances[best_idx]

    centerline, coverage = _instance_to_centerline(best_kps, W, H)

    # Confidence: blend LF score + coverage (same logic as our extractor)
    conf_base = coverage
    if era == "faded":
        conf_base *= 0.7
    elif era == "fine-grid":
        conf_base *= 0.9
    if blue_pct < 0.05:
        conf_base *= 0.6
    confidence = round(min(conf_base, 1.0), 3)

    return {
        "file": tile_path.name,
        "year": year, "month": month,
        "era": era,
        "grid_py": round(grid_py, 1),
        "grid_px": round(grid_px, 1),
        "blue_pct": round(blue_pct, 4),
        "coverage": round(coverage, 3),
        "confidence": confidence,
        "centerline": centerline,
        "lf_instance_count": len(instances),
        "lf_instance_scores": [round(s, 4) for s in scores],
        "lf_selected_instance": best_idx,
    }


def detect_all_instances(
    tile_path: Path,
    to_clean: bool = False,
) -> list[dict]:
    """
    Return ALL LineFormer instances for a tile (useful for Aug 1835 red series).
    Each item: {"index": i, "score": s, "centerline": [...], "coverage": f}
    """
    import cv2
    import numpy as np
    from curve_extractor import _to_gray, detect_grid_spacing, measure_blue_pct, classify_era

    _ensure_model()
    import infer
    import line_utils

    img_bgr = cv2.imread(str(tile_path))
    if img_bgr is None:
        raise FileNotFoundError(str(tile_path))
    H, W = img_bgr.shape[:2]

    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    gray = _to_gray(rgb)
    grid_py, grid_px = detect_grid_spacing(gray)
    blue_pct = measure_blue_pct(rgb)
    era = classify_era(grid_py, blue_pct)

    instances = line_utils.points_to_array(infer.get_dataseries(img_bgr, to_clean=to_clean))

    result = []
    for i, inst in enumerate(instances):
        cl, cov = _instance_to_centerline(inst, W, H)
        score = _score_instance(inst, H, W)
        # Sample original image to infer ink colour at keypoints
        bgr_samples = []
        for kp in inst[:50]:   # sample first 50 keypoints
            x, y = int(kp[0]), int(kp[1])
            if 0 <= x < W and 0 <= y < H:
                bgr_samples.append(img_bgr[y, x].tolist())
        mean_bgr = [round(float(np.mean([s[c] for s in bgr_samples])), 1)
                    for c in range(3)] if bgr_samples else [0, 0, 0]

        result.append({
            "index": i,
            "score": round(score, 4),
            "coverage": round(cov, 3),
            "centerline": cl,
            "mean_bgr_at_keypoints": mean_bgr,
            "likely_colour": (
                "blue" if mean_bgr[0] < mean_bgr[2] else
                "red"  if mean_bgr[2] < mean_bgr[0] * 0.7 else
                "dark"
            ),
        })
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    import argparse, json
    parser = argparse.ArgumentParser(
        description="Run LineFormer on a single ICE LEVEL tile."
    )
    parser.add_argument("tile", help="Path to tile JPEG")
    parser.add_argument("--all-instances", action="store_true",
                        help="Show all detected instances (useful for Aug 1835)")
    parser.add_argument("--to-clean", action="store_true",
                        help="Apply LineFormer's clean_chart preprocessing")
    args = parser.parse_args(argv)

    path = Path(args.tile)
    if args.all_instances:
        instances = detect_all_instances(path, to_clean=args.to_clean)
        print(f"{len(instances)} instances detected:")
        for inst in instances:
            print(f"  [{inst['index']}] score={inst['score']}  cov={inst['coverage']}  "
                  f"colour={inst['likely_colour']}  bgr={inst['mean_bgr_at_keypoints']}")
    else:
        result = extract_curve_lineformer(path, to_clean=args.to_clean)
        for k, v in result.items():
            if k != "centerline":
                print(f"  {k:30s}: {v}")
        print(f"  {'centerline':<30s}: [{len(result['centerline'])} entries]")


if __name__ == "__main__":
    main()
