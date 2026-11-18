"""
W1 + W2: Build manifest_v2.json and scaffold the gold annotation set.

Produces
--------
  manifest_v2.json          — 240-tile canonical manifest with SHA-256,
                               source scan, era, calibration skeleton,
                               annotation status.  Excludes tiles-3 duplicates.
  gold_set/                 — directory with 24 selected tiles (copied),
                               annotation_manifest.json, and per-tile stubs
                               for mask and stage CSV.
  gold_set/ANNOTATE.md      — annotation instructions.

Run
---
  python build_manifest_v2.py
  python build_manifest_v2.py --no-copy   # skip copying tile images
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── Tile directories (tiles 3 deliberately omitted — byte-identical to tiles 2) ──
TILE_DIRS = [
    "tiles_1_1835-1837_plus_code/tiles",
    "tiles",
    "tiles 2",
    "tiles 4",
    "tiles 5",
    "tiles 6",
    "tiles 7",
    "tiles 8",
]

# ── Scan ID → metadata (from auto_pipeline.py KNOWN_META) ──────────────────
SCAN_META: dict[int, dict] = {
    1835: {"scan": "210012", "station": "Ulm",     "form": "1830s-50s"},
    1836: {"scan": "210013", "station": "Ulm",     "form": "1830s-50s"},
    1837: {"scan": "210015", "station": "Ulm",     "form": "1830s-50s"},
    1839: {"scan": "210018", "station": "Ulm",     "form": "1830s-50s"},
    1845: {"scan": "210024", "station": "Ulm/Neu-Ulm (split Jul)", "form": "1830s-50s"},
    1848: {"scan": "210027", "station": "Neu-Ulm", "form": "1830s-50s"},
    1849: {"scan": "210028", "station": "Neu-Ulm", "form": "1830s-50s"},
    1850: {"scan": "210029", "station": "Neu-Ulm", "form": "1830s-50s"},
    1862: {"scan": "210042", "station": "Neu-Ulm", "form": "1862-63"},
    1863: {"scan": "210043", "station": "Neu-Ulm", "form": "1862-63"},
    1864: {"scan": "210044", "station": "Neu-Ulm", "form": "unclassified"},
    1865: {"scan": "210045", "station": "Neu-Ulm", "form": "unclassified"},
    1872: {"scan": "210053", "station": "Neu-Ulm", "form": "fine-grid"},
    1873: {"scan": "210054", "station": "Neu-Ulm", "form": "fine-grid"},
    1877: {"scan": "210058", "station": "Neu-Ulm", "form": "fine-grid"},
    1878: {"scan": "210059", "station": "Neu-Ulm", "form": "fine-grid"},
    1883: {"scan": "210064", "station": "Neu-Ulm", "form": "unclassified"},
    1890: {"scan": "210071", "station": "Neu-Ulm", "form": "unclassified"},
    1891: {"scan": "210072", "station": "Neu-Ulm", "form": "unclassified"},
    1893: {"scan": "210074", "station": "Neu-Ulm", "form": "unclassified"},
}

# ── Calibration skeleton per form ───────────────────────────────────────────
CALIBRATION: dict[str, dict] = {
    "1830s-50s":    {"grid_px_x": 24.0, "grid_px_y": 24.0, "stage_unit": None, "minor_unit_m": None, "note": "Side scale not yet transcribed"},
    "1862-63":      {"grid_px_x": 23.5, "grid_px_y": 23.5, "stage_unit": None, "minor_unit_m": None, "note": "Side scale not yet transcribed"},
    "fine-grid":    {"grid_px_x": 24.0, "grid_px_y": 16.0, "stage_unit": None, "minor_unit_m": None, "note": "16 px stage rulings; side scale not yet transcribed"},
    "unclassified": {"grid_px_x": 23.5, "grid_px_y": 23.0, "stage_unit": None, "minor_unit_m": None, "note": "Form unclassified; inspect TIFF header"},
}

# ── Known special flags ─────────────────────────────────────────────────────
SPECIAL_FLAGS: dict[str, list[str]] = {
    "1837-04": ["pasted-sheet", "hand-checked-box"],
    "1837-05": ["pasted-sheet", "hand-checked-box"],
    "1837-06": ["pasted-sheet", "hand-checked-box"],
    "1837-07": ["pasted-sheet", "hand-checked-box"],
    "1837-08": ["pasted-sheet", "hand-checked-box"],
    "1837-09": ["pasted-sheet", "hand-checked-box"],
    "1835-08": ["red-ink-series"],
    "1848-01": ["repaired-base"],
    "1848-02": ["repaired-base"],
    "1848-03": ["repaired-base"],
    "1845-10": ["repaired-base"],
    "1845-11": ["repaired-base"],
    "1845-12": ["repaired-base"],
}

FADED_YEARS = {1835, 1836, 1837, 1839}
FINE_GRID_YEARS = {1872, 1873, 1877, 1878}
WINTER_MONTHS = {11, 12, 1, 2, 3}

# ── 24 gold-set tile IDs: 2 per year × 12 years, era-stratified ─────────────
# Format: (year, month)
# Selection strategy:
#   - 1 winter month + 1 non-winter per year where possible
#   - Special tiles included: 1835-08 (red), 1837-04 (pasted), 1848-01 (repaired)
#   - 12 years span all 5 visual eras
GOLD_TILES = [
    (1835,  1),  # faded · winter     ← Ulm, ERA_FADED
    (1835,  8),  # faded · red series ← only red-ink tile in corpus
    (1836,  2),  # faded · winter
    (1836,  7),  # faded · summer
    (1837,  4),  # faded · pasted sheet
    (1837, 11),  # faded · winter + pasted
    (1839,  1),  # faded · winter
    (1839,  6),  # faded · summer
    (1848,  1),  # standard · winter · repaired base
    (1848,  8),  # standard · summer
    (1850,  2),  # standard · winter
    (1850,  9),  # standard · summer
    (1862, 12),  # 1862-63 · winter
    (1862,  5),  # 1862-63 · summer
    (1863,  3),  # 1862-63 · winter
    (1863,  7),  # 1862-63 · summer
    (1864,  1),  # unclassified · winter
    (1864,  8),  # unclassified · summer
    (1872,  1),  # fine-grid · winter
    (1872,  6),  # fine-grid · summer
    (1877, 12),  # fine-grid · winter
    (1877,  7),  # fine-grid · summer
    (1890,  2),  # later · winter
    (1890,  9),  # later · summer
]

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_unique_tiles() -> list[tuple[int, int, Path]]:
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


def build_manifest_v2(copy_gold: bool = True) -> None:
    tiles = collect_unique_tiles()
    print(f"Unique tiles found: {len(tiles)}")

    gold_ids = {(y, m) for y, m in GOLD_TILES}
    gold_dir = ROOT / "gold_set"
    gold_dir.mkdir(exist_ok=True)
    (gold_dir / "masks").mkdir(exist_ok=True)
    (gold_dir / "stage_csv").mkdir(exist_ok=True)

    records = []
    gold_records = []

    for year, month, path in tiles:
        tile_id = f"{year}-{month:02d}"
        sm = SCAN_META.get(year, {})
        form = sm.get("form", "unknown")
        cal = CALIBRATION.get(form, CALIBRATION["unclassified"])

        # Era label
        if year in FADED_YEARS:
            era = "faded"
        elif year in FINE_GRID_YEARS:
            era = "fine-grid"
        elif form == "1862-63":
            era = "1862-63"
        elif form == "unclassified":
            era = "later"
        else:
            era = "standard"

        flags = list(SPECIAL_FLAGS.get(tile_id, []))

        print(f"  SHA-256 {tile_id} … ", end="", flush=True)
        digest = sha256_file(path)
        print(f"{digest[:12]}…")

        is_gold = (year, month) in gold_ids
        is_winter = month in WINTER_MONTHS

        rec = {
            "tile_id": tile_id,
            "file": str(path.relative_to(ROOT)),
            "sha256": digest,
            "year": year,
            "month": month,
            "month_name": MONTHS[month - 1],
            "station": sm.get("station", "unknown"),
            "form": form,
            "era": era,
            "source_scan": sm.get("scan", "unknown"),
            "season": "winter" if is_winter else "summer",
            "calibration": {
                "grid_px_x": cal["grid_px_x"],
                "grid_px_y": cal["grid_px_y"],
                "stage_unit": cal["stage_unit"],
                "minor_unit_m": cal["minor_unit_m"],
                "calibration_note": cal["note"],
            },
            "flags": flags,
            "annotation": {
                "gold_set": is_gold,
                "mask_file": f"gold_set/masks/{tile_id}_mask.png" if is_gold else None,
                "stage_csv": f"gold_set/stage_csv/{tile_id}_stage.csv" if is_gold else None,
                "mask_complete": False,
                "stage_complete": False,
                "annotator": None,
                "annotation_date": None,
            },
            "ice_label": {
                "labelled": False,
                "week_styles": None,
                "has_ice": None,
                "has_jam": None,
                "label_date": None,
            } if is_winter else None,
        }
        records.append(rec)

        if is_gold:
            gold_records.append(rec)
            if copy_gold:
                dst = gold_dir / path.name
                if not dst.exists():
                    shutil.copy2(path, dst)
                    print(f"    copied {path.name} → gold_set/")
            # Stub mask placeholder (empty file so annotator knows what to create)
            stub = gold_dir / "masks" / f"{tile_id}_mask_STUB.txt"
            if not stub.exists():
                stub.write_text(
                    f"Replace this file with {tile_id}_mask.png\n"
                    f"Binary PNG, 744×3000 px, white=curve, black=background.\n"
                    f"Source tile: {path.name}\n"
                    f"Era: {era}  Form: {form}  Season: {'winter' if is_winter else 'summer'}\n"
                    f"Flags: {flags or 'none'}\n"
                )
            # Stub stage CSV
            csv_stub = gold_dir / "stage_csv" / f"{tile_id}_stage_STUB.csv"
            if not csv_stub.exists():
                csv_stub.write_text(
                    "day,stage_grid_units,notes\n"
                    + "\n".join(f"{d},," for d in range(1, 32))
                )

    # Write manifest_v2.json
    manifest = {
        "version": "2.0",
        "generated": str(date.today()),
        "tile_count": len(records),
        "gold_set_count": len(gold_records),
        "note": (
            "v2: covers all 240 unique tiles. tiles-3 (byte-identical duplicate of tiles-2) "
            "is excluded. Source scan IDs filled for all 20 years. "
            "Calibration fields are skeletons — stage_unit and minor_unit_m require "
            "manual transcription from TIFF side scales. "
            "annotation.gold_set marks the 24 tiles selected for hand-tracing."
        ),
        "tiles": records,
    }
    out = ROOT / "manifest_v2.json"
    out.write_text(json.dumps(manifest, indent=1))
    print(f"\n✓ manifest_v2.json  ({len(records)} tiles, {out.stat().st_size // 1024} KB)")

    # Write annotation manifest
    ann_manifest = {
        "total_gold_tiles": len(gold_records),
        "winter_tiles": sum(1 for r in gold_records if r["season"] == "winter"),
        "era_counts": {
            era: sum(1 for r in gold_records if r["era"] == era)
            for era in ["faded", "standard", "1862-63", "fine-grid", "later"]
        },
        "tiles": [
            {
                "tile_id": r["tile_id"],
                "file": path.name if copy_gold else r["file"],
                "year": r["year"],
                "month": r["month"],
                "era": r["era"],
                "season": r["season"],
                "flags": r["flags"],
                "mask_target": f"masks/{r['tile_id']}_mask.png",
                "stage_target": f"stage_csv/{r['tile_id']}_stage.csv",
            }
            for r, (_, _, path) in zip(
                gold_records,
                [(y, m, p) for y, m, p in tiles if (y, m) in gold_ids]
            )
        ],
    }
    (gold_dir / "annotation_manifest.json").write_text(
        json.dumps(ann_manifest, indent=2)
    )

    # Write annotation guide
    _write_annotation_guide(gold_dir)
    print(f"✓ gold_set/  ({len(gold_records)} tiles, {len([r for r in gold_records if r['season']=='winter'])} winter)")
    print(f"  Era breakdown: {ann_manifest['era_counts']}")


def _write_annotation_guide(gold_dir: Path) -> None:
    guide = """\
# ICE LEVEL Gold Set — Annotation Guide

## What to annotate

For each of the 24 tiles in this directory, you will produce two files:

### 1. Binary curve mask  (`masks/<id>_mask.png`)

- **Size**: 744 × 3000 px, same as the tile.
- **Format**: PNG, single channel (L mode) or RGB. White (255) = curve pixel, black (0) = everything else.
- **What to include**: the hand-drawn stage curve, including the light blue wash where it is clearly part of the line.
- **What to exclude**: the printed grid (vertical day rules, horizontal stage rules), the border, and any text.
- **Special tiles**:
  - `1835-08`: annotate the **blue** curve only. Annotate the red series separately in a second mask named `1835-08_mask_red.png`. Both are needed.
  - `1837-04` through `1837-09`: these are from a pasted sheet and have different borders. Annotate only the drawn curve, not the pasted page edge.
- **Tool**: LabelMe (`pip install labelme`) or CVAT (https://app.cvat.ai). Save as a filled polygon or pixel mask.
- **Resolution guide**: the curve is typically 2–6 px wide. For faded-era tiles (1835–1839), annotate the visible trace even if faint — do not expand to cover gaps.

### 2. Stage values in grid units  (`stage_csv/<id>_stage.csv`)

- **Format**: CSV with columns `day, stage_grid_units, notes`.
- **`day`**: 1–31 (or 1–28/30 as appropriate for the month).
- **`stage_grid_units`**: the y-position of the curve on that day, expressed as the number of minor grid cells from the bottom of the chart. One grid cell = 24 px (or 16 px for fine-grid era tiles 1872, 1877).
- **How to measure**: in an image editor, note the pixel y-coordinate of the curve centroid and divide by the grid cell height. The chart bottom is approximately y = 2900 px; subtract and divide.
- **Missing days**: leave `stage_grid_units` blank and add a note (e.g., "curve absent", "gap start", "ice likely").
- **Ice months**: for winter tiles, add notes: "dashed", "gap", "jam spike" as appropriate.

## Era-specific notes

| Era | Years | Challenge |
|-----|-------|-----------|
| Faded | 1835–1839 | Blue ink very pale; curve may be almost invisible in some segments. Annotate only what is clearly curve. |
| Standard | 1848–1850 | Good visibility. Watch for grid lines crossing the curve. |
| 1862–63 | 1862–1863 | Denser printing; some bleed between grid and curve. |
| Fine-grid | 1872, 1877 | Grid cells are 16 px, not 24. Use 16 px per grid unit for stage CSV. |
| Later | 1864, 1890 | Form unclassified; inspect the full TIFF header before annotating. |

## Quality standard

A mask is acceptable for training if a second annotator's mask has pixel IoU ≥ 0.80 with yours.
When in doubt, mark borderline pixels as background (conservative mask) rather than curve.
Add a note in `annotation_manifest.json` → `tiles[n].annotation_note` if the tile is damaged,
ambiguous, or has an unusual feature.

## Output check

After annotating tile `1848-01`:
- `gold_set/masks/1848-01_mask.png` — 744 × 3000, binary PNG  ✓
- `gold_set/stage_csv/1848-01_stage.csv` — 31 rows, day 1–31  ✓
- Delete the corresponding `*_STUB.txt` files when done.

Run `python eval_extractor.py --gold gold_set/` once masks are ready to compare
the automated extractor against your annotations.
"""
    (gold_dir / "ANNOTATE.md").write_text(guide)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-copy", action="store_true",
                        help="Skip copying tile images to gold_set/")
    args = parser.parse_args()
    build_manifest_v2(copy_gold=not args.no_copy)


if __name__ == "__main__":
    main()
