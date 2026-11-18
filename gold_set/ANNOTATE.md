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
