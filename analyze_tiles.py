"""
Master analysis runner — curve extraction + ice classification for all tiles.

Finds every unique tile in the dataset, runs curve_extractor.py + ice_classifier.py
on each one, and writes two output files:
  out/curve_results.json   — full extraction results
  out/ice_results.json     — ice classification results
  out/analysis_summary.json — aggregated stats

Usage
─────
  python analyze_tiles.py                        # writes to ./analysis_out/
  python analyze_tiles.py --out /path/to/out     # custom output dir
  python analyze_tiles.py --year 1848            # single year
  python analyze_tiles.py --limit 24             # first N tiles (dev mode)

The script deduplicates tiles (tiles 2 / tiles 3 are identical — only one copy
is processed), and processes tiles in year-month order.

Dependencies: numpy, opencv-python, Pillow (from curve_extractor / ice_classifier)
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TILE_DIRS = [
    "tiles_1_1835-1837_plus_code/tiles",
    "tiles",
    "tiles 2",
    "tiles 4",
    "tiles 5",
    "tiles 6",
    "tiles 7",
    "tiles 8",
    # tiles 3 is a duplicate of tiles 2 — intentionally omitted
]


def collect_unique_tiles() -> list[tuple[int, int, Path]]:
    """
    Return sorted list of (year, month, path) for each unique tile.
    When a tile appears in multiple directories (duplicate), only the first
    directory in TILE_DIRS order is kept.
    """
    seen: set[tuple[int, int]] = set()
    result = []
    for d in TILE_DIRS:
        folder = ROOT / d
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.jpg")):
            m = re.match(r"^(\d{4})_(\d{2})_[A-Z][a-z]{2}\.jpg$", p.name)
            if not m:
                continue
            key = (int(m.group(1)), int(m.group(2)))
            if key not in seen:
                seen.add(key)
                result.append((key[0], key[1], p))
    return sorted(result)


def run_all(
    out_dir: Path,
    year_filter: int | None = None,
    limit: int | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Import here so the script can be imported for unit testing without
    # triggering heavy imports at module load
    from curve_extractor import extract_curve
    from ice_classifier import analyse_tile

    tiles = collect_unique_tiles()
    if year_filter:
        tiles = [(y, m, p) for y, m, p in tiles if y == year_filter]
    if limit:
        tiles = tiles[:limit]

    print(f"Processing {len(tiles)} tiles → {out_dir}\n")

    curve_results = []
    ice_results   = []

    for year, month, tile_path in tiles:
        print(f"  {tile_path.name} … ", end="", flush=True)

        # Curve extraction
        try:
            ext = extract_curve(
                tile_path,
                year=year,
                month=month,
                save_mask=False,
                out_dir=out_dir,
            )
        except Exception as exc:
            print(f"EXTRACTION ERROR: {exc}")
            ext = {
                "file": tile_path.name, "year": year, "month": month,
                "era": "unknown", "grid_py": 0, "grid_px": 0,
                "blue_pct": 0, "coverage": 0.0, "confidence": 0.0,
                "centerline": [],
            }

        # Ice classification
        try:
            ice = analyse_tile(
                year=year,
                month=month,
                centerline=ext["centerline"],
                coverage=ext["coverage"],
            )
            ice["era"]        = ext.get("era")
            ice["confidence"] = ext.get("confidence")
        except Exception as exc:
            print(f"ICE ERROR: {exc}")
            ice = {
                "id": f"{year}-{month:02d}",
                "year": year, "month": month,
                "ice_class": "unknown", "ice_score": 0.0,
            }

        print(
            f"era={ext.get('era','?')[:3]}  "
            f"cov={ext['coverage']:.2f}  "
            f"ice={ice.get('ice_class','?')}"
        )

        curve_results.append(ext)
        ice_results.append(ice)

    # Save outputs
    (out_dir / "curve_results.json").write_text(json.dumps(curve_results, indent=1))
    (out_dir / "ice_results.json").write_text(json.dumps(ice_results, indent=1))

    # Summary
    summary = _build_summary(curve_results, ice_results)
    (out_dir / "analysis_summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\n{'─'*60}")
    print(f"Tiles processed : {len(tiles)}")
    print(f"Mean coverage   : {summary['mean_coverage']:.2f}")
    print(f"Ice detections  : {summary['ice_summary']}")
    print(f"Outputs in      : {out_dir}")


def _build_summary(curve_results: list[dict], ice_results: list[dict]) -> dict:
    from collections import Counter

    total = len(curve_results)
    if total == 0:
        return {}

    coverages = [r["coverage"] for r in curve_results]
    confidences = [r["confidence"] for r in curve_results]
    era_counts = Counter(r.get("era", "unknown") for r in curve_results)

    ice_classes = Counter(r.get("ice_class", "unknown") for r in ice_results)
    winter_ice = [
        r for r in ice_results
        if r.get("season") == "winter" and r.get("ice_class") in ("likely", "confirmed")
    ]

    # Per-year ice stats
    per_year: dict[int, list] = defaultdict(list)
    for r in ice_results:
        y = r.get("year")
        if y:
            per_year[y].append(r)

    year_ice = {
        y: {
            "total": len(recs),
            "ice_months": sum(1 for r in recs if r.get("ice_class") in ("likely","confirmed","possible")),
            "mean_ice_score": round(sum(r.get("ice_score",0) for r in recs) / len(recs), 3),
        }
        for y, recs in sorted(per_year.items())
    }

    return {
        "tile_count": total,
        "mean_coverage": round(sum(coverages) / total, 3),
        "mean_confidence": round(sum(confidences) / total, 3),
        "coverage_distribution": {
            "0.0-0.2": sum(1 for c in coverages if c < 0.2),
            "0.2-0.5": sum(1 for c in coverages if 0.2 <= c < 0.5),
            "0.5-0.8": sum(1 for c in coverages if 0.5 <= c < 0.8),
            "0.8-1.0": sum(1 for c in coverages if c >= 0.8),
        },
        "era_counts": dict(era_counts),
        "ice_summary": dict(ice_classes),
        "winter_ice_count": len(winter_ice),
        "per_year": year_ice,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run curve extraction + ice classification on all tiles."
    )
    parser.add_argument("--out", default="analysis_out", metavar="DIR")
    parser.add_argument("--year", type=int, default=None, metavar="YYYY")
    parser.add_argument("--limit", type=int, default=None, metavar="N")
    args = parser.parse_args(argv)

    run_all(Path(args.out), year_filter=args.year, limit=args.limit)


if __name__ == "__main__":
    main()
