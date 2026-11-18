"""
Ice-condition classifier for ICE LEVEL DATASET tiles.

The way a curve is drawn encodes river-ice conditions:
  • Solid continuous line   → open water, gauge reading active
  • Dashed / interrupted    → partial ice cover, intermittent readings
  • Absent (gap)            → full ice cover, gauge inaccessible or frozen
  • Anomalously high curve  → ice jam (stage elevation above normal)

This module analyses the per-day curve coverage computed by curve_extractor.py
and produces:
  1. A per-day coverage array: 0–1 for each day column.
  2. Gap intervals: (start_day, end_day) where the curve is absent.
  3. A line-style classification per week: solid / dashed / gap.
  4. An overall ice-risk score for the month.
  5. A detected-ice classification: none / possible / likely / confirmed.

Usage
─────
  python ice_classifier.py 1848_01_Jan.jpg                 # single tile
  python ice_classifier.py --results curve_results.json   # from extractor JSON
  python ice_classifier.py --batch tiles/ --out results/

  # Combine with the extractor:
  python curve_extractor.py --batch tiles/ --no-mask --out results/
  python ice_classifier.py  --results results/curve_results.json

Output
──────
  ice_results.json  — per-tile dict:
    { "id": "1848-01",
      "year": 1848, "month": 1, "season": "winter",
      "coverage": 0.72,
      "gap_fraction": 0.28,
      "gaps": [[3, 7], [15, 18]],          # day ranges (1-indexed, inclusive)
      "line_style_weeks": ["solid","dashed","gap","solid"],
      "ice_score": 0.61,
      "ice_class": "possible" }

Dependencies: numpy  (curve_extractor optional — can run standalone on tiles)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np

# ── Constants ──────────────────────────────────────────────────────────────────

# Winter months where gaps are more plausibly ice
WINTER_MONTHS = {11, 12, 1, 2, 3, 4}
SUMMER_MONTHS = {5, 6, 7, 8, 9, 10}

# Thresholds
GAP_THRESHOLD        = 0.15   # column coverage below this = gap day
DASHED_MIN_COV       = 0.15   # minimum to be "dashed" rather than pure gap
DASHED_MAX_COV       = 0.70   # maximum for "dashed" (above = solid)
DASHED_MIN_FREQ_PX   = 5      # minimum period in px for a dashed pattern
DASHED_MAX_FREQ_PX   = 30     # maximum period in px
ICE_RISK_WINTER_MULT = 1.0    # seasonal multiplier for ice risk
ICE_RISK_SUMMER_MULT = 0.3    # gaps in summer are less likely to be ice

# Ice-class thresholds on ice_score
ICE_SCORE_NONE      = 0.15
ICE_SCORE_POSSIBLE  = 0.35
ICE_SCORE_LIKELY    = 0.60

# ── Core signal ────────────────────────────────────────────────────────────────

def build_coverage_signal(centerline: list[list], W: int = 744) -> np.ndarray:
    """
    Build a 1-D coverage signal (length W) from a centerline list.
    Each element is 1.0 if a y-coordinate exists for that x, 0.0 otherwise.

    centerline: list of [x, y_or_null] from curve_extractor output.
    """
    cov = np.zeros(W, dtype=float)
    for entry in centerline:
        x, y = entry[0], entry[1]
        if y is not None:
            cov[int(x)] = 1.0
    return cov


def _days_to_cols(days_in_month: int, W: int = 744) -> float:
    """Return approximate column-width per day."""
    return W / days_in_month


def coverage_per_day(cov_signal: np.ndarray, days_in_month: int = 31) -> np.ndarray:
    """
    Bin the per-column coverage signal into per-day bins.
    Returns array of length days_in_month with mean coverage per day.
    """
    W = len(cov_signal)
    bins = np.array_split(cov_signal, days_in_month)
    return np.array([float(b.mean()) for b in bins])


def detect_gaps(day_cov: np.ndarray, threshold: float = GAP_THRESHOLD) -> list[tuple[int, int]]:
    """
    Identify contiguous gap intervals (1-indexed day ranges, inclusive).
    A 'gap day' is a day whose per-day coverage falls below `threshold`.
    Returns list of (start_day, end_day) tuples.
    """
    gaps = []
    in_gap = False
    start = 0
    for i, c in enumerate(day_cov):
        if c < threshold:
            if not in_gap:
                in_gap = True
                start = i
        else:
            if in_gap:
                gaps.append((start + 1, i))  # 1-indexed, inclusive
                in_gap = False
    if in_gap:
        gaps.append((start + 1, len(day_cov)))
    return gaps


# ── Line-style detection ────────────────────────────────────────────────────────

def _is_dashed(week_signal: np.ndarray) -> bool:
    """
    Detect a periodic dashed pattern in a week-length coverage signal.

    A dashed line has alternating present/absent at a regular period
    (5–30 px).  We test this via autocorrelation: if there is a significant
    local peak in the autocorrelation between lags 5–30, the signal is periodic.
    """
    if len(week_signal) < 20:
        return False
    mean_cov = week_signal.mean()
    if mean_cov < DASHED_MIN_COV or mean_cov > DASHED_MAX_COV:
        return False

    sig = week_signal.astype(float) - mean_cov
    ac = np.correlate(sig, sig, "full")
    mid = len(ac) // 2
    ac = ac[mid + DASHED_MIN_FREQ_PX : mid + DASHED_MAX_FREQ_PX + 1]
    if ac.size == 0:
        return False

    # Normalise
    ac_norm = ac / (ac[0] if ac[0] != 0 else 1.0)
    return bool(np.max(ac_norm) > 0.4)


def classify_line_style_weekly(
    cov_signal: np.ndarray,
    days_in_month: int = 31,
    W: int = 744,
) -> list[str]:
    """
    Classify the line style for each week of the month.

    Returns a list of strings: "solid" | "dashed" | "gap"
    """
    week_starts = [0, W * 7 // days_in_month, W * 14 // days_in_month,
                   W * 21 // days_in_month]
    week_ends = week_starts[1:] + [W]

    styles = []
    for ws, we in zip(week_starts, week_ends):
        seg = cov_signal[ws:we]
        mean = float(seg.mean())
        if mean < GAP_THRESHOLD:
            styles.append("gap")
        elif _is_dashed(seg):
            styles.append("dashed")
        else:
            styles.append("solid")
    return styles


# ── Ice-risk scoring ───────────────────────────────────────────────────────────

def ice_risk_score(
    gap_fraction: float,
    has_dashed: bool,
    month: int,
    gap_start_early: bool,
    gap_end_late: bool,
) -> float:
    """
    Compute a 0–1 ice risk score from several signals.

    Factors:
      gap_fraction  : fraction of month-days with absent curve
      has_dashed    : at least one week shows a dashed pattern
      month         : calendar month (winter months up-weighted)
      gap_start_early: gap begins in the first third of the month
      gap_end_late  : gap ends in the last third of the month
    """
    if month in WINTER_MONTHS:
        season_w = ICE_RISK_WINTER_MULT
    else:
        season_w = ICE_RISK_SUMMER_MULT

    score = 0.0
    # Gap fraction contribution (up to 0.5)
    score += min(gap_fraction * season_w, 0.5)
    # Dashed line contribution (up to 0.25)
    if has_dashed:
        score += 0.20 * season_w
    # Early-start + late-end (classic ice pattern: freeze → thaw within month)
    if gap_start_early and gap_end_late:
        score += 0.15 * season_w
    # Early January / February / March are highest risk
    if month in {12, 1, 2}:
        score += 0.10

    return round(min(score, 1.0), 3)


def ice_class(score: float) -> str:
    if score < ICE_SCORE_NONE:
        return "none"
    if score < ICE_SCORE_POSSIBLE:
        return "possible"
    if score < ICE_SCORE_LIKELY:
        return "likely"
    return "confirmed"


# ── Full analysis ───────────────────────────────────────────────────────────────

def analyse_tile(
    *,
    year: int | None,
    month: int | None,
    centerline: list[list],
    coverage: float,
    days_in_month: int | None = None,
    W: int = 744,
) -> dict:
    """
    Full ice-condition analysis for a single tile, given the centerline
    output from curve_extractor.

    If days_in_month is None, it is inferred from month (or defaults to 31).
    """
    if days_in_month is None:
        days_in_month = _days_in(year, month)

    # 1. Per-column coverage signal
    cov_signal = build_coverage_signal(centerline, W=W)

    # 2. Per-day coverage
    day_cov = coverage_per_day(cov_signal, days_in_month=days_in_month)
    gap_fraction = float((day_cov < GAP_THRESHOLD).mean())

    # 3. Gap intervals
    gaps = detect_gaps(day_cov)

    # 4. Line-style classification
    week_styles = classify_line_style_weekly(cov_signal, days_in_month=days_in_month, W=W)
    has_dashed = "dashed" in week_styles

    # 5. Gap position flags
    n = len(day_cov)
    gap_start_early = any(s <= n // 3 for s, e in gaps)
    gap_end_late    = any(e >= 2 * n // 3 for s, e in gaps)

    # 6. Ice risk
    score = ice_risk_score(
        gap_fraction=gap_fraction,
        has_dashed=has_dashed,
        month=month if month else 1,
        gap_start_early=gap_start_early,
        gap_end_late=gap_end_late,
    )
    cls = ice_class(score)

    season = "winter" if (month or 1) in WINTER_MONTHS else "summer"

    return {
        "id": f"{year}-{month:02d}" if year and month else "unknown",
        "year": year,
        "month": month,
        "season": season,
        "days_in_month": days_in_month,
        "coverage": round(float(coverage), 3),
        "gap_fraction": round(gap_fraction, 3),
        "gaps": [[int(s), int(e)] for s, e in gaps],
        "line_style_weeks": week_styles,
        "has_dashed": has_dashed,
        "ice_score": score,
        "ice_class": cls,
        "day_coverage": [round(float(c), 3) for c in day_cov],
    }


def _days_in(year: int | None, month: int | None) -> int:
    """Return days in month (simple, non-leap-aware for 1835-1893 is usually fine)."""
    if month is None:
        return 31
    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    # Leap years 1836, 1840, … not critical for digitisation purposes
    if month == 2 and year and (year % 4 == 0):
        days = 29
    return days


# ── Standalone tile mode (uses curve_extractor) ────────────────────────────────

def _run_on_tile(tile_path: Path, out_dir: Path | None) -> dict:
    """Extract curve and classify ice for a single tile file."""
    try:
        from curve_extractor import extract_curve
    except ImportError:
        print("ERROR: curve_extractor.py not found — place it in the same directory.")
        sys.exit(1)

    import re
    m = re.match(r"(\d{4})_(\d{2})", tile_path.name)
    year  = int(m.group(1)) if m else None
    month = int(m.group(2)) if m else None

    ext_result = extract_curve(tile_path, year=year, month=month,
                               save_mask=False, out_dir=out_dir)
    result = analyse_tile(
        year=year,
        month=month,
        centerline=ext_result["centerline"],
        coverage=ext_result["coverage"],
    )
    result["era"]        = ext_result.get("era")
    result["confidence"] = ext_result.get("confidence")
    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ice-condition classifier for ICE LEVEL tiles.")
    parser.add_argument("tile", nargs="?", help="Single tile path")
    parser.add_argument("--results", metavar="JSON",
                        help="Existing curve_results.json from curve_extractor")
    parser.add_argument("--batch", metavar="DIR",
                        help="Process all *.jpg tiles in this directory")
    parser.add_argument("--out", metavar="DIR", default=".",
                        help="Output directory for ice_results.json")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []

    if args.results:
        # Read pre-extracted centerlines
        ext_data = json.loads(Path(args.results).read_text())
        for rec in ext_data:
            result = analyse_tile(
                year=rec.get("year"),
                month=rec.get("month"),
                centerline=rec.get("centerline", []),
                coverage=rec.get("coverage", 0.0),
            )
            result["era"]        = rec.get("era")
            result["confidence"] = rec.get("confidence")
            print(f"  {result['id']:10s}  gaps={result['gap_fraction']:.2f}"
                  f"  style={result['line_style_weeks']}"
                  f"  ice={result['ice_class']}")
            results.append(result)

    elif args.batch:
        for tile_path in sorted(Path(args.batch).glob("*.jpg")):
            print(f"  {tile_path.name} … ", end="", flush=True)
            result = _run_on_tile(tile_path, out_dir)
            print(f"coverage={result['coverage']:.2f}  ice={result['ice_class']}")
            results.append(result)

    elif args.tile:
        result = _run_on_tile(Path(args.tile), out_dir)
        print(json.dumps(result, indent=2))
        results.append(result)
    else:
        parser.print_help()
        sys.exit(1)

    out_json = out_dir / "ice_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=1)
    print(f"\nSaved {len(results)} results → {out_json}")

    # Print summary
    if results:
        from collections import Counter
        cls_count = Counter(r["ice_class"] for r in results)
        winter_ice = sum(1 for r in results if r["season"] == "winter" and r["ice_class"] in ("likely", "confirmed"))
        print(f"\nSummary:")
        for cls, n in sorted(cls_count.items()):
            print(f"  {cls:12s} {n:4d}")
        print(f"  Winter months with likely/confirmed ice: {winter_ice}")


if __name__ == "__main__":
    main()
