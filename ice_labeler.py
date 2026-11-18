"""
W9: Ice-condition labelling tool for ICE LEVEL DATASET winter tiles.

Loads a tile's pre-computed centerline (from curve_results.json or by running
curve_extractor.py) and displays a week-by-week summary to guide labelling.
Labels are saved to ice_labels.json.

Usage
─────
  # Interactive: label all unlabelled winter tiles
  python ice_labeler.py --results analysis_out/curve_results.json

  # Label a single tile by ID
  python ice_labeler.py --id 1848-01 --results analysis_out/curve_results.json

  # Non-interactive: set all unlabelled winter tiles to 'needs-review'
  python ice_labeler.py --init-stubs

  # Print current label summary
  python ice_labeler.py --summary

Label schema (per tile)
──────────────────────
  {
    "tile_id": "1848-01",
    "year": 1848, "month": 1,
    "labelled": true,
    "week_styles": ["solid", "gap", "gap", "solid"],  // weeks 1–4
    "has_ice": true,       // any week is dashed or gap in a winter month
    "has_jam": false,      // anomalously high curve (z-score > 2 vs annual median)
    "ice_free_days": [],   // list of day numbers known to be ice-free
    "note": "",
    "labeller": "",
    "label_date": "2026-11-18"
  }

Week style vocabulary
─────────────────────
  solid   : continuous curve, open water
  dashed  : intermittent curve, partial ice or slush
  gap     : no curve, full ice cover or missing observation
  jam     : curve present but anomalously high (ice jam backwater)
  unclear : cannot determine from image alone

Dependencies: none (pure Python).  Run analyze_tiles.py first to get curve_results.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABELS_FILE = ROOT / "ice_labels.json"

WINTER_MONTHS = {11, 12, 1, 2, 3}
VALID_STYLES = {"solid", "dashed", "gap", "jam", "unclear"}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


def load_labels() -> dict:
    if LABELS_FILE.exists():
        return json.loads(LABELS_FILE.read_text())
    return {"version": "1.0", "labels": {}}


def save_labels(data: dict) -> None:
    LABELS_FILE.write_text(json.dumps(data, indent=2))


def _label_stub(tile_id: str, year: int, month: int) -> dict:
    return {
        "tile_id": tile_id,
        "year": year,
        "month": month,
        "labelled": False,
        "week_styles": [None, None, None, None],
        "has_ice": None,
        "has_jam": None,
        "ice_free_days": [],
        "note": "",
        "labeller": "",
        "label_date": None,
    }


def init_stubs(curve_results_path: Path) -> None:
    """Create unlabelled stubs for all winter tiles in curve_results.json."""
    data = load_labels()
    results = json.loads(curve_results_path.read_text())
    created = 0
    for r in results:
        year, month = r.get("year"), r.get("month")
        if month not in WINTER_MONTHS:
            continue
        tile_id = f"{year}-{month:02d}"
        if tile_id not in data["labels"]:
            data["labels"][tile_id] = _label_stub(tile_id, year, month)
            created += 1
    save_labels(data)
    print(f"Created {created} stubs in {LABELS_FILE}")


def print_summary(data: dict) -> None:
    labels = data["labels"]
    total = len(labels)
    done  = sum(1 for l in labels.values() if l["labelled"])
    ice   = sum(1 for l in labels.values() if l.get("has_ice"))
    jam   = sum(1 for l in labels.values() if l.get("has_jam"))

    print(f"\nIce label summary ({LABELS_FILE.name})")
    print(f"  Total winter tiles : {total}")
    print(f"  Labelled           : {done}")
    print(f"  Unlabelled         : {total - done}")
    print(f"  Ice detected       : {ice}")
    print(f"  Ice jam flagged    : {jam}")

    if done > 0:
        style_counts: dict[str, dict[str, int]] = {}
        for lbl in labels.values():
            if not lbl["labelled"]:
                continue
            for i, ws in enumerate(lbl["week_styles"]):
                week = f"W{i+1}"
                style_counts.setdefault(week, {})
                style_counts[week][ws or "none"] = \
                    style_counts[week].get(ws or "none", 0) + 1
        print("\n  Week style counts (labelled tiles only):")
        for wk, counts in sorted(style_counts.items()):
            row = "  ".join(f"{s}={n}" for s, n in sorted(counts.items()))
            print(f"    {wk}: {row}")


def _week_summary_from_centerline(centerline: list, days_in_month: int = 31) -> list[str]:
    """
    Compute rough weekly coverage from a centerline for display during labelling.
    Returns ["cov=0.XX", …] for 4 weeks.
    """
    W = len(centerline)
    week_starts = [0, W * 7 // days_in_month, W * 14 // days_in_month,
                   W * 21 // days_in_month]
    week_ends = week_starts[1:] + [W]
    summaries = []
    for ws, we in zip(week_starts, week_ends):
        seg = centerline[ws:we]
        cov = sum(1 for _, y in seg if y is not None) / max(len(seg), 1)
        summaries.append(f"cov={cov:.2f}")
    return summaries


def interactive_label(
    tile_id: str,
    curve_results: dict,
    labeller: str,
) -> dict | None:
    """Interactive terminal labelling for one tile."""
    r = curve_results.get(tile_id)
    if r is None:
        print(f"  No curve result found for {tile_id}")
        return None

    year, month = r.get("year"), r.get("month")
    era = r.get("era", "?")
    cov = r.get("coverage", 0)
    conf = r.get("confidence", 0)
    cl = r.get("centerline", [])
    week_covs = _week_summary_from_centerline(cl)

    print(f"\n── {tile_id}  ({MONTHS[month-1]} {year})  era={era}  cov={cov:.2f}  conf={conf:.2f}")
    print(f"   Week coverage: W1={week_covs[0]}  W2={week_covs[1]}  W3={week_covs[2]}  W4={week_covs[3]}")
    print(f"   Style options: solid / dashed / gap / jam / unclear")

    styles = []
    for wk in range(1, 5):
        while True:
            val = input(f"   Week {wk} style [{week_covs[wk-1]}]: ").strip().lower()
            if not val:
                # Auto-suggest based on coverage
                c = float(week_covs[wk-1].split("=")[1])
                val = "gap" if c < 0.15 else "solid"
                print(f"   → auto: {val}")
            if val in VALID_STYLES:
                styles.append(val)
                break
            print(f"   Must be one of: {', '.join(sorted(VALID_STYLES))}")

    has_ice = any(s in ("dashed", "gap") for s in styles)
    jam_q   = input("   Ice jam? (y/N): ").strip().lower()
    has_jam = jam_q in ("y", "yes")
    note    = input("   Note (press Enter to skip): ").strip()

    return {
        "tile_id": tile_id,
        "year": year,
        "month": month,
        "labelled": True,
        "week_styles": styles,
        "has_ice": has_ice,
        "has_jam": has_jam,
        "ice_free_days": [],
        "note": note,
        "labeller": labeller,
        "label_date": str(date.today()),
    }


def run_interactive(curve_results_path: Path, target_id: str | None, labeller: str) -> None:
    results_raw = json.loads(curve_results_path.read_text())
    # Build dict keyed by tile_id
    curve_results = {}
    for r in results_raw:
        y, m = r.get("year"), r.get("month")
        if y and m:
            curve_results[f"{y}-{m:02d}"] = r

    data = load_labels()
    if not data["labels"]:
        print("No stubs found. Run: python ice_labeler.py --init-stubs --results <path>")
        return

    targets = (
        [target_id]
        if target_id
        else [tid for tid, lbl in data["labels"].items() if not lbl["labelled"]]
    )

    if not targets:
        print("All winter tiles are already labelled. Use --summary to review.")
        return

    print(f"\nLabelling {len(targets)} tile(s). Ctrl+C to stop (progress saved).\n")

    try:
        for tid in targets:
            result = interactive_label(tid, curve_results, labeller)
            if result:
                data["labels"][tid] = result
                save_labels(data)
                print(f"   ✓ saved {tid}")
    except KeyboardInterrupt:
        print("\nInterrupted — labels saved.")

    print_summary(data)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Ice-condition labelling tool for ICE LEVEL winter tiles."
    )
    parser.add_argument("--results", metavar="JSON",
                        help="Path to curve_results.json from analyze_tiles.py")
    parser.add_argument("--init-stubs", action="store_true",
                        help="Create unlabelled stubs for all winter tiles")
    parser.add_argument("--id", metavar="TILE_ID",
                        help="Label a single tile (e.g. 1848-01)")
    parser.add_argument("--summary", action="store_true",
                        help="Print label summary and exit")
    parser.add_argument("--labeller", default="",
                        help="Your name/initials for attribution")
    args = parser.parse_args(argv)

    if args.summary:
        print_summary(load_labels())
        return

    if args.init_stubs:
        if not args.results:
            parser.error("--init-stubs requires --results <curve_results.json>")
        init_stubs(Path(args.results))
        return

    if args.results:
        run_interactive(
            curve_results_path=Path(args.results),
            target_id=args.id,
            labeller=args.labeller,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
