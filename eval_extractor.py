"""
W4: Evaluate the curve extractor against the hand-annotated gold set.

For each gold-set tile that has a completed mask, runs curve_extractor.py
and computes:
  - Pixel IoU          : intersection over union of predicted mask vs. gold mask
  - Centerline MAE     : mean absolute y-error (pixels) on days where both
                         the prediction and the gold agree a curve is present
  - Coverage error     : |predicted coverage - gold coverage|

Results are broken down by era and written to baseline_eval.json.

Usage
─────
  # After annotating gold tiles:
  python eval_extractor.py --gold gold_set/

  # Compare against LineFormer wrapper output:
  python eval_extractor.py --gold gold_set/ --extractor lineformer

  # Single tile:
  python eval_extractor.py --tile gold_set/1848_01_Jan.jpg --mask gold_set/masks/1848-01_mask.png

Dependencies: numpy, opencv-python, Pillow (same as curve_extractor.py)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
FADED_YEARS      = {1835, 1836, 1837, 1839}
FINE_GRID_YEARS  = {1872, 1873, 1877, 1878}


def _era(year: int, form: str = "") -> str:
    if year in FADED_YEARS:    return "faded"
    if year in FINE_GRID_YEARS: return "fine-grid"
    if form == "1862-63":       return "1862-63"
    return "standard"


def compute_iou(pred_mask, gold_mask) -> float:
    import numpy as np
    p = (pred_mask > 127).astype(bool)
    g = (gold_mask  > 127).astype(bool)
    inter = (p & g).sum()
    union = (p | g).sum()
    return float(inter / union) if union > 0 else 0.0


def compute_centerline_mae(pred_cl: list, gold_cl: list) -> float:
    """
    Mean absolute y-error (pixels) where BOTH prediction and gold have a curve.
    pred_cl / gold_cl: list of [x, y_or_null] from extract_curve output or
    list of (y_or_None,) indexed by x.
    """
    import numpy as np
    errors = []
    for x, (p_entry, g_entry) in enumerate(zip(pred_cl, gold_cl)):
        p_y = p_entry[1] if isinstance(p_entry, (list, tuple)) else p_entry
        g_y = g_entry[1] if isinstance(g_entry, (list, tuple)) else g_entry
        if p_y is not None and g_y is not None:
            errors.append(abs(p_y - g_y))
    return float(sum(errors) / len(errors)) if errors else float("nan")


def evaluate_tile(tile_path: Path, gold_mask_path: Path, extractor: str = "ours") -> dict:
    import numpy as np
    from PIL import Image

    m = re.match(r"(\d{4})_(\d{2})", tile_path.name)
    year  = int(m.group(1)) if m else None
    month = int(m.group(2)) if m else None
    tile_id = f"{year}-{month:02d}" if year and month else tile_path.stem

    gold_arr = np.asarray(Image.open(gold_mask_path).convert("L"), dtype=np.uint8)

    # Build gold centerline from mask (column centroid)
    H, W = gold_arr.shape
    gold_cl = []
    gold_coverage = 0
    for x in range(W):
        col = gold_arr[:, x]
        ys = (col > 127).nonzero()[0]
        if ys.size:
            gold_cl.append([x, float(ys.mean())])
            gold_coverage += 1
        else:
            gold_cl.append([x, None])
    gold_coverage_pct = gold_coverage / W

    # Run extractor
    if extractor == "ours":
        from curve_extractor import extract_curve
        result = extract_curve(tile_path, year=year, month=month,
                               save_mask=False, out_dir=None)
        pred_cl = result["centerline"]
        pred_coverage = result["coverage"]
        era = result["era"]
        confidence = result["confidence"]

        # Reconstruct predicted mask from centerline for IoU
        pred_mask = np.zeros((H, W), dtype=np.uint8)
        for entry in pred_cl:
            x, y = entry[0], entry[1]
            if y is not None:
                for dy in range(-3, 4):   # 7-px band around centerline
                    yy = int(round(y)) + dy
                    if 0 <= yy < H:
                        pred_mask[yy, x] = 255

    elif extractor == "lineformer":
        from lineformer_wrapper import extract_curve_lineformer
        result = extract_curve_lineformer(tile_path, year=year, month=month)
        pred_cl = result["centerline"]
        pred_coverage = result["coverage"]
        era = result.get("era", _era(year or 0))
        confidence = result.get("confidence", 0.0)
        pred_mask = np.zeros((H, W), dtype=np.uint8)
        for entry in pred_cl:
            x, y = entry[0], entry[1]
            if y is not None:
                for dy in range(-3, 4):
                    yy = int(round(y)) + dy
                    if 0 <= yy < H:
                        pred_mask[yy, x] = 255
    else:
        raise ValueError(f"Unknown extractor: {extractor}")

    iou = compute_iou(pred_mask, gold_arr)
    mae = compute_centerline_mae(pred_cl, gold_cl)
    cov_err = abs(pred_coverage - gold_coverage_pct)

    return {
        "tile_id": tile_id,
        "year": year,
        "month": month,
        "era": era if extractor == "ours" else _era(year or 0),
        "extractor": extractor,
        "confidence": confidence,
        "iou": round(iou, 4),
        "centerline_mae_px": round(mae, 2) if not __import__("math").isnan(mae) else None,
        "coverage_error": round(cov_err, 4),
        "pred_coverage": round(pred_coverage, 4),
        "gold_coverage": round(gold_coverage_pct, 4),
    }


def run_evaluation(gold_dir: Path, extractor: str, out_path: Path) -> None:
    ann_manifest_path = gold_dir / "annotation_manifest.json"
    if not ann_manifest_path.exists():
        print(f"ERROR: {ann_manifest_path} not found. Run build_manifest_v2.py first.")
        sys.exit(1)

    ann = json.loads(ann_manifest_path.read_text())
    results = []

    for tile_info in ann["tiles"]:
        tile_id = tile_info["tile_id"]
        year    = tile_info["year"]
        month   = tile_info["month"]
        tile_name = f"{year}_{month:02d}_{MONTHS[month-1]}.jpg"
        tile_path = gold_dir / tile_name
        mask_path = gold_dir / "masks" / f"{tile_id}_mask.png"

        if not tile_path.exists():
            print(f"  SKIP {tile_id}: tile not found at {tile_path}")
            continue
        if not mask_path.exists():
            print(f"  SKIP {tile_id}: mask not annotated yet ({mask_path})")
            continue

        print(f"  eval {tile_id} ({tile_info['era']}) … ", end="", flush=True)
        try:
            r = evaluate_tile(tile_path, mask_path, extractor=extractor)
            print(f"IoU={r['iou']:.3f}  MAE={r['centerline_mae_px']}px  cov_err={r['coverage_error']:.3f}")
            results.append(r)
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({"tile_id": tile_id, "error": str(exc), "extractor": extractor})

    if not results:
        print("No completed masks found. Annotate at least one tile first.")
        return

    # Per-era summary
    era_groups: dict[str, list[dict]] = {}
    for r in results:
        if "iou" not in r:
            continue
        era = r.get("era", "unknown")
        era_groups.setdefault(era, []).append(r)

    era_summary = {}
    for era, recs in sorted(era_groups.items()):
        ious  = [r["iou"] for r in recs]
        maes  = [r["centerline_mae_px"] for r in recs if r.get("centerline_mae_px") is not None]
        era_summary[era] = {
            "n": len(recs),
            "mean_iou": round(sum(ious) / len(ious), 4),
            "mean_mae_px": round(sum(maes) / len(maes), 2) if maes else None,
        }

    all_ious  = [r["iou"] for r in results if "iou" in r]
    all_maes  = [r["centerline_mae_px"] for r in results
                 if r.get("centerline_mae_px") is not None]
    summary = {
        "extractor": extractor,
        "tiles_evaluated": len(results),
        "mean_iou":     round(sum(all_ious) / len(all_ious), 4) if all_ious else None,
        "mean_mae_px":  round(sum(all_maes) / len(all_maes), 2) if all_maes else None,
        "per_era": era_summary,
    }

    output = {"summary": summary, "tiles": results}
    out_path.write_text(json.dumps(output, indent=2))

    print(f"\n── Summary ({'%s' % extractor}) ───────────────────────────")
    print(f"  Tiles evaluated : {summary['tiles_evaluated']}")
    print(f"  Mean IoU        : {summary['mean_iou']}")
    print(f"  Mean MAE (px)   : {summary['mean_mae_px']}")
    print(f"  Per era:")
    for era, s in era_summary.items():
        print(f"    {era:12s}  n={s['n']}  IoU={s['mean_iou']}  MAE={s['mean_mae_px']}px")
    print(f"\n  Results → {out_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate curve extractor against gold annotations."
    )
    parser.add_argument("--gold", metavar="DIR", default="gold_set",
                        help="Gold set directory (default: gold_set/)")
    parser.add_argument("--extractor", choices=["ours", "lineformer"], default="ours")
    parser.add_argument("--out", metavar="JSON", default=None,
                        help="Output path (default: baseline_eval.json or lineformer_eval.json)")
    parser.add_argument("--tile", metavar="PATH", help="Evaluate single tile")
    parser.add_argument("--mask", metavar="PATH", help="Gold mask for single tile")
    args = parser.parse_args(argv)

    if args.tile and args.mask:
        r = evaluate_tile(Path(args.tile), Path(args.mask), extractor=args.extractor)
        print(json.dumps(r, indent=2))
        return

    out_name = args.out or (
        "baseline_eval.json" if args.extractor == "ours" else "lineformer_eval.json"
    )
    run_evaluation(
        gold_dir=ROOT / args.gold,
        extractor=args.extractor,
        out_path=ROOT / out_name,
    )


if __name__ == "__main__":
    main()
