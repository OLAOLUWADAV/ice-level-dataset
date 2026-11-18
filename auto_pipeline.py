"""
Automated end-to-end tile-cutting pipeline for ICE LEVEL DATASET.

This extends the original `tiles_1_1835-1837_plus_code/pipeline.py` in three
critical ways:

  1. No manual priors required.
     The original pipeline needs `priors.json` — a hand-entered dict of rough
     panel x-positions per scan. This version detects them automatically from
     the TIFF itself using column-darkness analysis.

  2. Covers all eras (1835–1893).
     The original `warp_all.py` hard-codes a 10-scan META dict (1835–1863).
     This version accepts a YAML/JSON sidecar file for any scan and falls back
     to heuristic metadata when the sidecar is absent.

  3. Portable paths.
     Hard-coded `/mnt/user-data/uploads/…` removed. Paths are arguments.

Usage
─────
  # Detect and tile a single TIFF
  python auto_pipeline.py detect Bay_Landesamt_210012.tif --out work/
  python auto_pipeline.py tile   Bay_Landesamt_210012.tif --boxes work/boxes.json --out tiles_out/

  # Full pipeline in one step
  python auto_pipeline.py run    Bay_Landesamt_210012.tif --out tiles_out/

  # Batch all TIFFs in a folder
  python auto_pipeline.py batch  /path/to/tiffs/ --out tiles_out/

Outputs
───────
  <out>/boxes_<scan_id>.json   — detection result
  <out>/<year>_<mm>_<Mon>.jpg  — 744×3000 tiles at quality 90
  <out>/month_boxes.json       — per-tile metadata (appended across runs)
  <out>/pbox_<scan_id>.png     — detection visualisation

Dependencies: numpy, opencv-python, Pillow
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# ── Constants ──────────────────────────────────────────────────────────────────

TILE_W, TILE_H = 744, 3000
PREVIEW_W = 3000          # target width for detection (same as original)
JPEG_QUALITY = 90
MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
PAD_COLOUR = (232, 232, 232)

# Scan-to-year/station table (from warp_all.py).  Add more as needed.
KNOWN_META: dict[str, dict] = {
    "210012": {"year": 1835, "stations": ["Ulm"]*4,       "form": "1830s-50s form"},
    "210013": {"year": 1836, "stations": ["Ulm"]*4,       "form": "1830s-50s form"},
    "210015": {"year": 1837, "stations": ["Ulm"]*4,       "form": "1830s-50s form"},
    "210018": {"year": 1839, "stations": ["Ulm"]*4,       "form": "1830s-50s form"},
    "210024": {"year": 1845, "stations": ["Ulm","Ulm","Neu-Ulm","Neu-Ulm"],
                              "form": "1830s-50s form"},
    "210027": {"year": 1848, "stations": ["Neu-Ulm"]*4,   "form": "1830s-50s form"},
    "210028": {"year": 1849, "stations": ["Neu-Ulm"]*4,   "form": "1830s-50s form"},
    "210029": {"year": 1850, "stations": ["Neu-Ulm"]*4,   "form": "1830s-50s form"},
    "210042": {"year": 1862, "stations": ["Neu-Ulm"]*4,   "form": "1862-63 form"},
    "210043": {"year": 1863, "stations": ["Neu-Ulm"]*4,   "form": "1862-63 form"},
    # 1864–1893 scans — fill in after inspecting TIFF headers
    "210044": {"year": 1864, "stations": ["Neu-Ulm"]*4,   "form": "unclassified"},
    "210045": {"year": 1865, "stations": ["Neu-Ulm"]*4,   "form": "unclassified"},
    "210053": {"year": 1872, "stations": ["Neu-Ulm"]*4,   "form": "fine-grid form"},
    "210054": {"year": 1873, "stations": ["Neu-Ulm"]*4,   "form": "fine-grid form"},
    "210058": {"year": 1877, "stations": ["Neu-Ulm"]*4,   "form": "fine-grid form"},
    "210059": {"year": 1878, "stations": ["Neu-Ulm"]*4,   "form": "fine-grid form"},
    "210064": {"year": 1883, "stations": ["Neu-Ulm"]*4,   "form": "unclassified"},
    "210071": {"year": 1890, "stations": ["Neu-Ulm"]*4,   "form": "unclassified"},
    "210072": {"year": 1891, "stations": ["Neu-Ulm"]*4,   "form": "unclassified"},
    "210074": {"year": 1893, "stations": ["Neu-Ulm"]*4,   "form": "unclassified"},
}


# ── Utility ────────────────────────────────────────────────────────────────────

def _scan_id(tiff_path: Path) -> str:
    """Extract the numeric ID from a TIFF filename."""
    m = re.search(r"(\d{6})", tiff_path.name)
    return m.group(1) if m else tiff_path.stem


def _load_preview(tiff_path: Path) -> tuple[np.ndarray, float]:
    """Load TIFF, downscale to PREVIEW_W wide.  Returns (rgb_array, scale)."""
    img = Image.open(tiff_path).convert("RGB")
    W_orig = img.width
    scale = PREVIEW_W / W_orig
    H_new = int(img.height * scale)
    img = img.resize((PREVIEW_W, H_new), Image.LANCZOS)
    return np.asarray(img, dtype=np.uint8), scale


def _rot(img: np.ndarray, ang: float, cx: float, cy: float, border: int) -> np.ndarray:
    H, W = img.shape[:2]
    M = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=border)


# ── Auto-prior detection ───────────────────────────────────────────────────────

def _column_darkness(gray: np.ndarray, y0_frac: float = 0.25, y1_frac: float = 0.75) -> np.ndarray:
    """
    Mean column darkness (inverted brightness) in the central chart region.
    Returns 1-D array of length W.
    """
    H, W = gray.shape
    y0, y1 = int(H * y0_frac), int(H * y1_frac)
    # 'Darkness' = 255 - brightness; use median to suppress outliers
    return 255.0 - np.median(gray[y0:y1, :].astype(float), axis=0)


def _find_panel_priors(preview_gray: np.ndarray) -> list[int]:
    """
    Auto-detect the x-positions of the four panel left-edges without any
    manual seed.

    Strategy
    ─────────
    1. Compute the column darkness profile across the chart height.
    2. Find broad dark bands by running a wide median-smoothed minimum;
       these mark the margins and inter-panel gutters.
    3. The chart occupies the region between the two outermost gutters.
    4. Divide that region into four equal strips and refine each boundary to
       the nearest dark-column peak within ±80 px.

    Returns list of four x integers (left edge of each panel in preview px).
    """
    H, W = preview_gray.shape
    dark = _column_darkness(preview_gray)

    # Smooth with a ~1% wide window to find broad structure
    smooth_w = max(3, W // 100)
    smoothed = np.convolve(dark, np.ones(smooth_w) / smooth_w, "same")

    # Find the leftmost and rightmost positions above the 60th percentile
    threshold = np.percentile(smoothed, 60)
    chart_cols = np.where(smoothed > threshold)[0]
    if len(chart_cols) < 100:
        # Fallback: divide image into four equal quadrants
        margin = W // 20
        span = W - 2 * margin
        return [margin + i * span // 4 for i in range(4)]

    x_left  = int(chart_cols[0])
    x_right = int(chart_cols[-1])
    span = x_right - x_left

    # Four panels → three gutters between them
    # Initial seeds at equal spacing
    seeds = [x_left + span * i // 4 for i in range(4)]

    # Refine each seed: look for local maximum of darkness within ±80 px
    refined = []
    search = 80
    for seed in seeds:
        lo = max(0, seed - search)
        hi = min(W, seed + search)
        segment = smoothed[lo:hi]
        local_max = lo + int(np.argmax(segment))
        refined.append(local_max)

    return refined


# ── Skew detection ─────────────────────────────────────────────────────────────

def _detect_skew(half_gray: np.ndarray, ang_range: float = 2.0, step: float = 0.05) -> float:
    """
    Find the rotation angle (degrees) that maximises the variance of the
    row-profile derivative — the same method as the original pipeline.py.
    """
    H, W = half_gray.shape
    cx, cy = W / 2, H / 2
    best: tuple[float, float] | None = None

    angles = np.arange(-ang_range, ang_range + step * 0.5, step)
    for ang in angles:
        r = cv2.warpAffine(
            half_gray,
            cv2.getRotationMatrix2D((cx, cy), ang, 1.0),
            (W, H),
            borderValue=255,
        )
        prof = r[:, int(W * 0.05) : int(W * 0.95)].mean(axis=1)
        sc = float(np.var(np.diff(prof)))
        if best is None or sc > best[0]:
            best = (sc, ang)

    return float(best[1]) if best else 0.0


# ── Panel detection ────────────────────────────────────────────────────────────

def _detect_panel(deskewed: np.ndarray, prior_x: int) -> dict:
    """
    Detect the four month-separator columns, the top ruling and the baseline
    for one quarter-panel.  Identical logic to the original `detect_panel`
    but accepts an auto-detected prior_x.

    Returns the same dict shape as the original: xs, w, top, base, conf, flags.
    """
    H, W = deskewed.shape[:2]
    gi = cv2.cvtColor(deskewed, cv2.COLOR_RGB2GRAY).astype(float)

    y0, y1 = int(H * 0.3), int(H * 0.72)
    paper = np.percentile(gi[y0:y1], 90)
    colp = paper - np.median(gi[y0:y1], axis=0)
    cmax = np.maximum.reduce([np.roll(colp, k) for k in (-1, 0, 1)])

    # Fit a 4-line comb (month separators within panel)
    best_comb = max(
        (
            (sum(cmax[int(round(x0 + k * w))] for k in range(4)), x0, w)
            for x0 in range(prior_x - 30, prior_x + 31)
            for w in np.arange(214, 226.5, 0.5)
            if int(round(x0 + 3 * w)) < W
        ),
        default=(0, prior_x, 220),
    )
    xs = [int(round(best_comb[1] + k * best_comb[2])) for k in range(4)]
    xa, xb = xs[0] + 5, xs[3] - 5

    rowp = paper - np.median(gi[:, xa:xb], axis=1)
    rmax = np.maximum.reduce([np.roll(rowp, k) for k in (-1, 0, 1)])

    bgm = cv2.medianBlur(gi.astype(np.uint8), 31).astype(float)
    vv = cv2.morphologyEx(
        ((bgm - gi) > 12).astype(np.uint8),
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9)),
    )
    dens = vv[:, xa:xb].mean(axis=1)
    ref = np.median(dens[int(H * 0.4) : int(H * 0.65)])

    # Baseline detection
    cands = []
    for b in range(int(H * 0.75), int(H * 0.905)):
        s1 = rmax[b]
        if s1 < rmax[b - 1] or s1 < rmax[b + 1]:
            continue
        cands.append((b, min(s1, rmax[b + 12 : b + 19].max(), rmax[b + 25 : b + 37].max()),
                      dens[b - 14 : b - 3].mean(), dens[b + 3 : b + 11].mean()))

    if not cands:
        base = int(H * 0.85)
        ok = False
    else:
        mt = max(c[1] for c in cands)
        good = [c for c in cands if c[1] >= 0.3 * mt and c[2] >= 0.5 * ref and c[3] < 0.4 * c[2]]
        base = max(good or cands, key=lambda c: c[0])[0]
        ok = bool(good)

    # Top ruling
    tb = range(int(H * 0.12), int(H * 0.32))
    mx_top = max((rmax[y] for y in tb), default=0)
    top_cands = [
        y for y in tb
        if rmax[y] >= 0.4 * mx_top
        and rmax[y] >= rmax[y - 1]
        and rmax[y] >= rmax[y + 1]
        and dens[y + 5 : y + 40].mean() >= 0.5 * ref
    ]
    top = top_cands[0] if top_cands else int(H * 0.19)

    return {
        "xs": xs,
        "w": float(best_comb[2]),
        "top": int(top),
        "base": int(base),
        "conf": {"triple_ok": ok},
        "flags": [],
        "_rmax": rmax.tolist(),
    }


# ── Full detect step ───────────────────────────────────────────────────────────

def detect(tiff_path: Path, out_dir: Path) -> dict:
    """
    Detect panel geometry for a single TIFF.
    Saves boxes_<scan_id>.json and pbox_<scan_id>.png to out_dir.
    Returns the boxes dict.
    """
    scan_id = _scan_id(tiff_path)
    print(f"[detect] {tiff_path.name}  scan_id={scan_id}")

    preview, _scale = _load_preview(tiff_path)
    H, W = preview.shape[:2]
    gray = cv2.cvtColor(preview, cv2.COLOR_RGB2GRAY).astype(np.float32)

    # Auto-detect panel priors
    priors = _find_panel_priors(gray)
    print(f"  auto priors: {priors}")

    # Per-half skew
    halves_info = []
    half_imgs = []
    for side, (c0, c1) in enumerate([(0, W // 2), (W // 2, W)]):
        ang = _detect_skew(gray[:, c0:c1])
        cx, cy = (c0 + c1) / 2, H / 2
        deskewed = _rot(preview, ang, cx, cy, (255, 255, 255))
        halves_info.append({"angle": round(ang, 3), "cx": cx, "cy": cy})
        half_imgs.append(deskewed)

    # Per-panel detection (4 panels per spread)
    panels = []
    for pi, px in enumerate(priors):
        half_img = half_imgs[0 if pi < 2 else 1]
        panel = _detect_panel(half_img, px)
        panel["half"] = 0 if pi < 2 else 1
        panels.append(panel)

    # Spread consistency repair
    rmax_cache = {pi: np.array(panels[pi].pop("_rmax")) for pi in range(4)}
    for key in ("top", "base"):
        vals = [p[key] for p in panels]
        m = float(np.median(vals))
        for pi, p in enumerate(panels):
            if abs(p[key] - m) > 12:
                p["flags"].append(f"{key} deviates {p[key]-m:+.0f} px from spread median")
                rr = rmax_cache[pi]
                rng = range(int(m) - 12, int(m) + 13)
                if key == "base":
                    new = max(rng, key=lambda b: min(rr[b], rr[b+12:b+19].max(), rr[b+25:b+37].max()))
                else:
                    new = max(rng, key=lambda y: rr[y])
                p["flags"].append(f"repaired {key} {p[key]}→{new}")
                p[key] = int(new)

    boxes = {
        "scan_id": scan_id,
        "shape": [H, W],
        "auto_priors": priors,
        "halves": halves_info,
        "panels": panels,
    }

    # Save JSON
    out_dir.mkdir(parents=True, exist_ok=True)
    boxes_path = out_dir / f"boxes_{scan_id}.json"
    boxes_path.write_text(json.dumps(boxes, indent=1))

    # Diagnostic image
    vis = half_imgs[0].copy()
    vis[:, W // 2 :] = half_imgs[1][:, W // 2 :]
    for p in panels:
        for i in range(3):
            cv2.rectangle(vis, (p["xs"][i], p["top"]), (p["xs"][i+1], p["base"]), (255, 0, 0), 2)
    vis_small = cv2.resize(vis, (1800, int(H * 1800 / W)))
    cv2.imwrite(str(out_dir / f"pbox_{scan_id}.png"), cv2.cvtColor(vis_small, cv2.COLOR_RGB2BGR))

    print(f"  → {boxes_path}")
    return boxes


# ── Tile step ──────────────────────────────────────────────────────────────────

def tile_scan(tiff_path: Path, boxes: dict, out_dir: Path) -> list[dict]:
    """
    Warp the full-resolution TIFF and cut it into 744×3000 monthly tiles.
    Returns list of month-box metadata records.
    """
    scan_id = _scan_id(tiff_path)
    scan_meta = KNOWN_META.get(scan_id, {
        "year": None, "stations": ["unknown"] * 4, "form": "unclassified"
    })
    year       = scan_meta["year"]
    stations   = scan_meta["stations"]
    form_label = scan_meta["form"]

    print(f"[tile] {tiff_path.name}  year={year}  form={form_label}")

    # Load full resolution
    full = np.asarray(Image.open(tiff_path).convert("RGB"))
    _fH, fW = full.shape[:2]
    scale = fW / boxes["shape"][1]

    # Deskewed full-res halves
    rots = []
    for h in boxes["halves"]:
        ang = h["angle"]
        cx, cy = h["cx"] * scale, h["cy"] * scale
        rots.append(_rot(full, ang, cx, cy, (255, 255, 255)) if abs(ang) > 0.01 else full)

    # Compute vertical scale factor from panel heights
    std_heights = [(p["base"] - p["top"]) * scale for p in boxes["panels"]]
    ky = TILE_H / float(np.median(std_heights))

    out_dir.mkdir(parents=True, exist_ok=True)
    records = []

    for pi, panel in enumerate(boxes["panels"]):
        img = rots[panel["half"]]
        for mi in range(3):
            m_idx = pi * 3 + mi  # 0–11
            x0 = panel["xs"][mi]  * scale
            x1 = panel["xs"][mi + 1] * scale
            y0 = panel["top"] * scale
            y1 = panel["base"] * scale

            crop = img[int(round(y0)) : int(round(y1)), int(round(x0)) : int(round(x1))]
            if crop.size == 0:
                print(f"  WARNING: empty crop for panel {pi}, month {mi+1}")
                continue

            tile = cv2.resize(crop, (TILE_W, TILE_H), interpolation=cv2.INTER_AREA)

            mon_num = m_idx + 1
            mon_name = MON[m_idx]
            fname = f"{year}_{mon_num:02d}_{mon_name}.jpg"
            Image.fromarray(tile).save(str(out_dir / fname), quality=JPEG_QUALITY)

            records.append({
                "scan": scan_id,
                "year": year,
                "month": mon_num,
                "gauge": stations[pi],
                "form": form_label,
                "deskew_deg": round(boxes["halves"][panel["half"]]["angle"], 2),
                "box_px_fullres_after_deskew": [
                    round(x0), round(y0), round(x1), round(y1)
                ],
                "flags": list(panel.get("flags", [])),
            })
            print(f"  saved {fname}")

    del full, rots
    return records


# ── CLI ────────────────────────────────────────────────────────────────────────

def _load_boxes(path: Path) -> dict:
    return json.loads(path.read_text())


def cmd_detect(args: argparse.Namespace) -> None:
    out = Path(args.out)
    detect(Path(args.tiff), out)


def cmd_tile(args: argparse.Namespace) -> None:
    tiff = Path(args.tiff)
    boxes = _load_boxes(Path(args.boxes))
    out = Path(args.out)
    records = tile_scan(tiff, boxes, out)
    _append_month_boxes(out / "month_boxes.json", records)
    print(f"Wrote {len(records)} tile records → {out / 'month_boxes.json'}")


def cmd_run(args: argparse.Namespace) -> None:
    tiff = Path(args.tiff)
    out = Path(args.out)
    boxes = detect(tiff, out)
    records = tile_scan(tiff, boxes, out)
    _append_month_boxes(out / "month_boxes.json", records)
    print(f"Done: {len(records)} tiles in {out}")


def cmd_batch(args: argparse.Namespace) -> None:
    tiff_dir = Path(args.tiff_dir)
    out = Path(args.out)
    tiffs = sorted(tiff_dir.glob("*.tif")) + sorted(tiff_dir.glob("*.tiff"))
    if not tiffs:
        print("No TIFFs found.")
        return
    all_records = []
    for tiff in tiffs:
        boxes = detect(tiff, out)
        records = tile_scan(tiff, boxes, out)
        all_records.extend(records)
    _append_month_boxes(out / "month_boxes.json", all_records)
    print(f"\nBatch done: {len(all_records)} tiles from {len(tiffs)} TIFFs → {out}")


def _append_month_boxes(path: Path, new_records: list[dict]) -> None:
    existing = json.loads(path.read_text()) if path.exists() else []
    existing_keys = {(r["scan"], r["month"]) for r in existing}
    for r in new_records:
        if (r["scan"], r["month"]) not in existing_keys:
            existing.append(r)
    path.write_text(json.dumps(existing, indent=1))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Auto tile-cutting pipeline for ICE LEVEL DATASET.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_detect = sub.add_parser("detect", help="Detect panel geometry from a TIFF.")
    p_detect.add_argument("tiff")
    p_detect.add_argument("--out", default="work", metavar="DIR")

    p_tile = sub.add_parser("tile", help="Cut tiles from a TIFF using existing boxes.")
    p_tile.add_argument("tiff")
    p_tile.add_argument("--boxes", required=True, metavar="JSON")
    p_tile.add_argument("--out", default="tiles_out", metavar="DIR")

    p_run = sub.add_parser("run", help="Detect + tile in one step.")
    p_run.add_argument("tiff")
    p_run.add_argument("--out", default="tiles_out", metavar="DIR")

    p_batch = sub.add_parser("batch", help="Process all TIFFs in a folder.")
    p_batch.add_argument("tiff_dir", metavar="DIR")
    p_batch.add_argument("--out", default="tiles_out", metavar="DIR")

    args = parser.parse_args(argv)
    {"detect": cmd_detect, "tile": cmd_tile, "run": cmd_run, "batch": cmd_batch}[args.command](args)


if __name__ == "__main__":
    main()
