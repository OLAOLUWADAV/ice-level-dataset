"""
Multi-era hydrograph curve extractor for ICE LEVEL DATASET tiles.

Usage:
    python curve_extractor.py 1849_01_Jan.jpg                 # single tile
    python curve_extractor.py --batch tiles_dir/ --out results/

Output per tile:
    <stem>_mask.png     — binary curve mask (white = curve pixels)
    <stem>_curve.json   — {"year":…, "month":…, "era":…, "grid_py":…,
                           "centerline": [[x, y], …],  (px; NaN gaps)
                           "coverage": 0.0–1.0, "confidence": 0.0–1.0}

The key challenges solved here
───────────────────────────────
 • 1835–1839: blue ink faded to near-zero; colour threshold detects ~0% blue.
   Solution: Retinex-style local background subtraction + hue-range fallback.
 • 1872–1878: stage-ruling spacing is 16 px instead of 24 px.
   Solution: grid-spacing auto-detection; all downstream calibration is relative.
 • Grid interference: printed rules cross the curve.
   Solution: morphological long-line extraction then masking.
 • Wash bleed: broad low-saturation halo around the curve.
   Solution: post-process with connected-component selection, not raw dilation.

Dependencies: numpy, opencv-python, Pillow
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np
from PIL import Image


# ── Era constants ──────────────────────────────────────────────────────────────

class Era(NamedTuple):
    name: str
    grid_py: float       # measured stage-ruling spacing (px)
    grid_px: float       # measured day spacing (px)
    blue_strict: bool    # True if blue ink is legible without Retinex


ERA_FINE_GRID   = "1872-1878"
ERA_STANDARD    = "standard"
ERA_FADED       = "faded"       # 1835-1839 (ink too pale for colour threshold)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_rgb(path: Path) -> np.ndarray:
    """Load image as uint8 H×W×3 RGB."""
    img = Image.open(path).convert("RGB")
    return np.asarray(img, dtype=np.uint8)


def _to_gray(rgb: np.ndarray) -> np.ndarray:
    """Standard luminance, 0–255 float32."""
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)


def _paper_contrast(gray: np.ndarray) -> np.ndarray:
    """
    Convert brightness to 'darkness above paper'.
    Uses a large Gaussian to estimate local paper tone, then returns
    how much darker each pixel is.  Result is 0–255 float32.
    """
    bg = cv2.GaussianBlur(gray, (0, 0), sigmaX=31, sigmaY=31)
    contrast = np.clip(bg - gray, 0, 255).astype(np.float32)
    return contrast


# ── Era / grid detection ────────────────────────────────────────────────────────

def detect_grid_spacing(gray: np.ndarray) -> tuple[float, float]:
    """
    Return (grid_py, grid_px): typical horizontal-ruling spacing (rows)
    and vertical-ruling spacing (cols) in pixels, measured from the tile.

    Uses autocorrelation of the median profile; robust to missing lines.
    """
    H, W = gray.shape

    def _autocorr_peak(profile: np.ndarray, lo: int = 10, hi: int = 45) -> float:
        sig = profile.astype(float) - profile.mean()
        ac = np.correlate(sig, sig, "full")[len(sig) - 1:]
        segment = ac[lo : hi + 1]
        if segment.size == 0:
            return 24.0
        return float(lo + np.argmax(segment))

    # Use middle 50% of the image to avoid borders
    y0, y1 = H // 4, 3 * H // 4
    x0, x1 = W // 4, 3 * W // 4

    row_prof = np.median(gray[y0:y1, x0:x1], axis=1)
    col_prof = np.median(gray[y0:y1, x0:x1], axis=0)

    grid_py = _autocorr_peak(row_prof, lo=10, hi=45)
    grid_px = _autocorr_peak(col_prof, lo=18, hi=30)

    return grid_py, grid_px


FADED_YEARS     = {1835, 1836, 1837, 1839}
FINE_GRID_YEARS = {1872, 1873, 1877, 1878}


def classify_era(grid_py: float, blue_pct: float, year: int | None = None) -> str:
    """
    Assign an era label.  Year-based classification is authoritative when
    year is known; grid_py and blue_pct serve as fallbacks for unknown years.
    """
    if grid_py < 20:
        return ERA_FINE_GRID
    if year is not None:
        if year in FADED_YEARS:
            return ERA_FADED
        if year in FINE_GRID_YEARS:
            return ERA_FINE_GRID
        return ERA_STANDARD
    # Year unknown — fall back to Retinex blue_pct heuristic
    if blue_pct < 0.015:
        return ERA_FADED
    return ERA_STANDARD


def measure_blue_pct(rgb: np.ndarray) -> float:
    """
    Return fraction of pixels that are locally bluer than their neighbourhood.

    Historical scans have warm (yellowish) paper: absolute B < R everywhere.
    We use a Retinex-style measure: pixels where B is high relative to the
    local background B, and B-channel relative excess exceeds R-channel excess.
    This works across all eras including faded tiles.
    """
    b = rgb[..., 2].astype(np.float32)
    r = rgb[..., 0].astype(np.float32)

    blur_b = cv2.GaussianBlur(b, (0, 0), sigmaX=61, sigmaY=61)
    blur_r = cv2.GaussianBlur(r, (0, 0), sigmaX=61, sigmaY=61)

    with np.errstate(divide="ignore", invalid="ignore"):
        rel_b = b / np.maximum(blur_b, 1.0)
        rel_r = r / np.maximum(blur_r, 1.0)

    mask = (rel_b - rel_r) > 0.04   # locally bluer than red
    return float(mask.mean())


# ── Grid removal ───────────────────────────────────────────────────────────────

def build_grid_mask(gray: np.ndarray, grid_py: float, grid_px: float) -> np.ndarray:
    """
    Return a uint8 binary mask (255 = grid pixel) by extracting long horizontal
    and vertical lines via morphological opening.

    The structuring element is 10× the grid spacing to target only lines that
    span many cells — the printed ruling, not the hand-drawn curve.
    """
    ink = (255 - gray.astype(np.uint8))  # invert: dark → bright

    h_len = max(5, int(grid_px * 10))
    v_len = max(5, int(grid_py * 10))

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))

    h_lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(ink, cv2.MORPH_OPEN, v_kernel)

    grid = np.maximum(h_lines, v_lines)

    # Slight dilation to absorb pixels adjacent to grid lines
    dil = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    grid = cv2.dilate(grid, dil, iterations=1)

    # Threshold at 100 — paper background ink values sit ~50–70 (gray≈190–205);
    # actual dark grid lines produce ink values > 100. Using 20 would flag the
    # entire paper background as grid.
    return (grid > 100).astype(np.uint8) * 255


# ── Colour segmentation ────────────────────────────────────────────────────────

def segment_curve_color(rgb: np.ndarray, era: str, gray: np.ndarray) -> np.ndarray:
    """
    Return a uint8 binary mask (255 = likely curve pixel) using colour cues.

    For ERA_FADED (1835-1839): blue ink is too pale for direct detection.
    Strategy: Retinex (local background subtraction) in HSV space.
    For ERA_STANDARD / ERA_FINE_GRID: direct blue-channel dominance.
    """
    r = rgb[..., 0].astype(np.int16)
    g = rgb[..., 1].astype(np.int16)
    b = rgb[..., 2].astype(np.int16)

    # All eras use Retinex (local background normalisation).
    # Historical scans have warm/yellowed paper (R > B globally), so absolute
    # blue-channel dominance never works.  We instead look for pixels that are
    # locally bluer and darker than their neighbourhood.
    #
    # ERA_FADED (1835–1839): ink is very pale — use a looser threshold.
    # ERA_STANDARD / ERA_FINE_GRID: ink is clearer — tighter threshold to
    #   reduce false positives on paper texture.

    blur_r = cv2.GaussianBlur(rgb[..., 0].astype(np.float32), (0, 0), 61)
    blur_g = cv2.GaussianBlur(rgb[..., 1].astype(np.float32), (0, 0), 61)
    blur_b = cv2.GaussianBlur(rgb[..., 2].astype(np.float32), (0, 0), 61)

    with np.errstate(divide="ignore", invalid="ignore"):
        rel_b = b.astype(float) / np.maximum(blur_b, 1)
        rel_r = r.astype(float) / np.maximum(blur_r, 1)
        rel_g = g.astype(float) / np.maximum(blur_g, 1)
        blue_rel = rel_b - 0.5 * rel_r - 0.5 * rel_g

    contrast = _paper_contrast(gray)

    # Use the same thresholds for every era: historical scans are warm-toned
    # (paper R > B) throughout, so aggressive Retinex is needed everywhere.
    # Era differences are captured in the confidence score, not in detection.
    retinex_thr  = 0.04
    contrast_thr = 4.0

    mask = (blue_rel > retinex_thr) & (contrast > contrast_thr)

    # Hue fallback: blue-cyan range in HSV (hue 88–135 in OpenCV 0–180 scale)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h_ch = hsv[..., 0].astype(np.int16)
    s_ch = hsv[..., 1].astype(np.int16)
    hue_blue = (h_ch >= 88) & (h_ch <= 135) & (s_ch > 15) & (contrast > 3.0)
    mask = mask | hue_blue

    return (mask.astype(np.uint8) * 255)


# ── Component selection ─────────────────────────────────────────────────────────

def _x_coverage(comp_pixels: np.ndarray, W: int) -> float:
    """Fraction of x-columns occupied by this component."""
    if comp_pixels.shape[0] == 0:
        return 0.0
    xs = np.unique(comp_pixels[:, 1])
    return len(xs) / W


def _continuity(comp_pixels: np.ndarray, W: int) -> float:
    """
    Fraction of occupied x-columns that have a neighbour within 3 columns.
    Measures how 'connected' the component is across the x-axis.
    """
    if comp_pixels.shape[0] == 0:
        return 0.0
    xs = set(np.unique(comp_pixels[:, 1]).tolist())
    n = sum(1 for x in xs if (x - 1) in xs or (x + 1) in xs or (x - 2) in xs or (x + 2) in xs)
    return n / max(len(xs), 1)


def _position_prior(comp_pixels: np.ndarray, H: int) -> float:
    """
    Returns 1.0 if the component centroid is in the lower 70% of the image
    (where the hydrograph curve normally sits), falling to 0.0 at the top.
    """
    if comp_pixels.shape[0] == 0:
        return 0.0
    cy = comp_pixels[:, 0].mean() / H
    # Favour: 0.3 < cy < 0.95
    if cy < 0.3:
        return max(0.0, cy / 0.3)
    return 1.0


def select_curve_component(raw_mask: np.ndarray, grid_mask: np.ndarray, grid_px: float = 24.0) -> np.ndarray:
    """
    Remove grid pixels from raw_mask, then find connected components and return
    a refined binary mask containing only the best hydrograph-curve component(s).

    Components are scored on:
      • x-coverage (should span >40% of tile width)
      • continuity  (should be a connected path, not scattered dots)
      • position prior (should sit in the lower image region)
      • size penalty (too small = noise; too large = grid residue)

    Returns uint8 binary mask (255 = curve).
    """
    H, W = raw_mask.shape

    # Remove grid
    candidate = raw_mask.copy()
    candidate[grid_mask > 0] = 0

    # Horizontal morphological closing reconnects curve segments that the
    # grid removal split apart.  Kernel is ~1 grid-cell wide so it bridges
    # gaps between day-rulings without merging unrelated blobs.
    close_w = max(5, int(grid_px * 1.5))
    h_close = cv2.getStructuringElement(cv2.MORPH_RECT, (close_w, 1))
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, h_close)

    # Also a small vertical close for 2-pixel-wide curves
    v_close = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, v_close)

    # Connected components
    num, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, connectivity=8)

    if num <= 1:
        return np.zeros_like(raw_mask)

    best_score = -1.0
    best_label = -1

    min_size = W // 2  # at least one pixel per 2 columns (handles ice gaps)

    for lab in range(1, num):
        area = stats[lab, cv2.CC_STAT_AREA]
        if area < min_size:
            continue
        ys, xs = np.where(labels == lab)
        pts = np.stack([ys, xs], axis=1)

        cov  = _x_coverage(pts, W)
        cont = _continuity(pts, W)
        pos  = _position_prior(pts, H)
        size_norm = min(area / (W * H * 0.02), 1.0)  # cap at 2% of tile

        score = cov * 0.5 + cont * 0.3 + pos * 0.1 + size_norm * 0.1

        if score > best_score and cov > 0.15:
            best_score = score
            best_label = lab

    if best_label < 0:
        return np.zeros_like(raw_mask)

    out = np.zeros_like(raw_mask)
    out[labels == best_label] = 255
    return out


# ── Centerline extraction ──────────────────────────────────────────────────────

def extract_centerline(
    curve_mask: np.ndarray,
    H: int, W: int,
) -> tuple[list[tuple[int, float | None]], float]:
    """
    For each x-column, compute the y-centroid of curve pixels.
    Returns:
        centerline: list of (x, y) with y=None where the curve is absent
        coverage:   fraction of columns with a detected point
    """
    centerline: list[tuple[int, float | None]] = []
    present = 0

    for x in range(W):
        col = curve_mask[:, x]
        ys = np.where(col > 0)[0]
        if ys.size == 0:
            centerline.append((x, None))
        else:
            cy = float(ys.mean())
            centerline.append((x, cy))
            present += 1

    # Median-filter the y-values to suppress single-pixel spikes
    raw_ys = np.array([y if y is not None else np.nan for _, y in centerline], dtype=float)
    valid = ~np.isnan(raw_ys)
    if valid.sum() > 10:
        smoothed = raw_ys.copy()
        win = 7
        for i in range(W):
            lo = max(0, i - win // 2)
            hi = min(W, i + win // 2 + 1)
            seg = raw_ys[lo:hi]
            seg = seg[~np.isnan(seg)]
            if seg.size > 0:
                smoothed[i] = float(np.median(seg))
        raw_ys = smoothed

    centerline = [
        (x, None if np.isnan(raw_ys[x]) else round(float(raw_ys[x]), 1))
        for x in range(W)
    ]
    coverage = present / W
    return centerline, coverage


# ── Confidence scoring ─────────────────────────────────────────────────────────

def score_confidence(coverage: float, era: str, blue_pct: float) -> float:
    """
    Heuristic confidence 0–1 for the extraction quality.
      • High coverage + good era  → high confidence
      • Faded era + low coverage  → low confidence
    """
    base = coverage
    if era == ERA_FADED:
        base *= 0.7
    elif era == ERA_FINE_GRID:
        base *= 0.9
    if blue_pct < 0.05:
        base *= 0.6
    return round(min(base, 1.0), 3)


# ── Top-level API ──────────────────────────────────────────────────────────────

def extract_curve(
    tile_path: Path,
    *,
    year: int | None = None,
    month: int | None = None,
    save_mask: bool = True,
    out_dir: Path | None = None,
) -> dict:
    """
    Full extraction pipeline for a single tile.

    Returns a dict with:
        era, grid_py, grid_px, blue_pct, coverage, confidence,
        centerline: [[x, y_or_null], …]
    Saves <stem>_mask.png if save_mask=True.
    """
    tile_path = Path(tile_path)
    rgb = _load_rgb(tile_path)
    H, W = rgb.shape[:2]
    gray = _to_gray(rgb)

    # 1. Measure grid + era
    grid_py, grid_px = detect_grid_spacing(gray)
    blue_pct = measure_blue_pct(rgb)
    era = classify_era(grid_py, blue_pct, year=year)

    # 2. Build grid mask
    grid_mask = build_grid_mask(gray, grid_py, grid_px)

    # 3. Colour segmentation
    raw_mask = segment_curve_color(rgb, era, gray)

    # 4. Component selection
    curve_mask = select_curve_component(raw_mask, grid_mask, grid_px=grid_px)

    # 5. Centerline
    centerline, coverage = extract_centerline(curve_mask, H, W)

    # 6. Confidence
    confidence = score_confidence(coverage, era, blue_pct)

    result = {
        "file": tile_path.name,
        "year": year,
        "month": month,
        "era": era,
        "grid_py": round(grid_py, 1),
        "grid_px": round(grid_px, 1),
        "blue_pct": round(blue_pct, 4),
        "coverage": round(coverage, 3),
        "confidence": confidence,
        "centerline": [[x, y] for x, y in centerline],
    }

    if save_mask:
        out = out_dir or tile_path.parent
        mask_path = out / (tile_path.stem + "_mask.png")
        Image.fromarray(curve_mask).save(mask_path)
        result["mask_file"] = str(mask_path)

    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_year_month(name: str) -> tuple[int | None, int | None]:
    import re
    m = re.match(r"(\d{4})_(\d{2})", name)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract hydrograph curves from ICE LEVEL tiles.")
    parser.add_argument("tile", nargs="?", help="Single tile path")
    parser.add_argument("--batch", metavar="DIR", help="Process all *.jpg in DIR")
    parser.add_argument("--out", metavar="DIR", default=None, help="Output directory")
    parser.add_argument("--no-mask", action="store_true", help="Skip saving mask images")
    args = parser.parse_args(argv)

    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    tiles: list[Path] = []
    if args.batch:
        tiles = sorted(Path(args.batch).glob("*.jpg"))
    elif args.tile:
        tiles = [Path(args.tile)]
    else:
        parser.print_help()
        sys.exit(1)

    results = []
    for tile_path in tiles:
        year, month = _parse_year_month(tile_path.name)
        print(f"  {tile_path.name} … ", end="", flush=True)
        result = extract_curve(
            tile_path,
            year=year,
            month=month,
            save_mask=not args.no_mask,
            out_dir=out_dir or tile_path.parent,
        )
        print(f"era={result['era']}  coverage={result['coverage']:.2f}  conf={result['confidence']:.2f}")
        results.append(result)

    out_json = (out_dir or Path(".")) / "curve_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=1)
    print(f"\nSaved {len(results)} results → {out_json}")


if __name__ == "__main__":
    main()
