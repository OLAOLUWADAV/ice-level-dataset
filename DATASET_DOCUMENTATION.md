# ICE LEVEL DATASET

## A critical dataset card and technical documentation

**Document date:** 23 October 2026  
**Scope:** the folder `/Users/mac/Downloads/ICE LEVEL DATASET` and its immediate source scans in `/Users/mac/Downloads`  
**Status:** working inventory and critical assessment, not a peer-reviewed datasheet  
**Prepared from:** direct inspection of every folder, all 26 TIFFs, the generation code, the two JSON metadata files, and a quantitative audit of all 240 unique monthly tiles

---

## 1. Executive summary

This folder is an **image corpus of nineteenth-century hydrological gauge charts**, not a table of numerical water levels. The charts record daily water levels at the gauges at **Ulm** and later **Neu-Ulm on the Danube**, in the territory of the former Kingdom of Bavaria. The source sheets are annual tables titled *“Tabelle, welche die Beobachtungen der Wasserhöhen … darstellt”* (“Table presenting the observations of water levels…”). The archive scans carry the series label **“Bayer. Landesamt für Wasserwirtschaft 21”** and are held by the **Bayerisches Hauptstaatsarchiv**.

The dataset contains:

- **26 archival TIFF scans**, about **2.5 GB**, roughly 10,000 × 4,400 px at **300 dpi**, scanned on **5 March 2025**.
- **240 unique monthly tiles** in JPEG format, **744 × 3000 px** each, covering **20 years between 1835 and 1893**.
- **24 duplicate JPEG files** (the folders `tiles 2` and `tiles 3` are byte-identical), giving **264 JPEG files** on disk and **162 MB** of tiles.
- Generation and metadata code: `pipeline.py`, `warp_all.py`, `priors.json`, `boxes_pipeline.json`, and `month_boxes.json`.
- Metadata for only **120 of the 240 tiles** (1835–1863). The other 120 tiles (1864–1893) have no per-tile metadata in this folder.

The central idea is valuable: a rare, visually consistent, multi-decade record of pre-instrumental water levels, suitable for historical hydrology, climate reconstruction, and research on chart-image understanding. The central problem is equally clear: **this is a raw image corpus, not an analysis-ready time series**. It has no extracted values, no units, no datum, no ground truth, no labels inside the tiles, no licence statement, and only partial metadata. The station changes from Ulm to Neu-Ulm, the chart forms and grid scales change, and the vertical and horizontal conventions are not explicitly documented per tile. It should be treated as a digitisation source and benchmark corpus, not as a finished dataset.

The folder name **“ICE LEVEL DATASET”** is not explained by the contents. The charts are water-level charts. A red-ink series appears in **August 1835** and may represent a second observation series or an ice-related annotation, but there is no legend or metadata to confirm that. Until the red series is resolved, the name should be treated as a working label, not a description of the measured variable.

---

## 2. What the dataset actually is

### 2.1 The physical source

Each TIFF is a single wide annual chart sheet. The 1835 sheet, for example, has four quarter-panels, each containing three monthly columns. Across the top of each panel is the handwritten title:

> *Tabelle, welche die Beobachtungen der Wasserhöhen, die am Wasserhöhenmaße zu Ulm dargestellt, für das Jahr 1835.*

Translation: “Table presenting the observations of water levels recorded at the water-level gauge at Ulm for the year 1835.”

Each monthly column is a graph-paper strip:

- The **horizontal axis** is the **day of the month**, from day 1 at the left to day 31 at the right, at approximately **24 pixels per day** in the tiles.
- The **vertical axis** is the **gauge stage** (water level), with the lowest stage near the bottom of the sheet and increasing upward.
- The blue hand-drawn line is the **stage hydrograph** for that month.
- A light blue wash often accompanies the line. It may be deliberate shading, ink bleed, or both; the dataset does not distinguish them.
- Thick rules every five minor grid cells help reading; a side scale is printed on the sheet, and the daily numbers are printed below the plot in the “day strip”.
- The annual sheet is a table of 12 such columns. The generation pipeline cuts the table into one image per month.

### 2.2 What the tiles contain, and what they do not

Each tile contains only the graph-paper plot area and the inked curve. It does **not** contain:

- the year,
- the month name,
- the station name,
- the axis units,
- the gauge datum,
- the day labels (the day strip is cropped away),
- any explanatory legend,
- any numeric table of observations.

Those facts live only on the full TIFF and, for the first ten years, partly in `month_boxes.json`. This is the single most important fact about the dataset: **the image is not self-describing.**

### 2.3 The red series

A quantitative colour audit found substantial red ink in only one tile: **August 1835** (4,232 red pixels). Occasional faint red pixels occur in other tiles, but no other tile has a comparable red trace. The red line in August 1835 is a separate series from the blue curve. It could be a second observer’s reading, a correction, an ice annotation, or an unrelated mark. There is no legend, no metadata field, and no code that handles it.

**Consequence:** the red series must be treated as an unresolved feature. It cannot be called “ice” without evidence from the source sheet or archival documentation.

---

## 3. Provenance and chain of custody

The TIFF metadata gives unusually good provenance:

| Property | Value |
|---|---|
| Holding institution | **Bayerisches Hauptstaatsarchiv** (also in the copyright tag) |
| Series title in TIFF | `Bayer. Landesamt für Wasserwirtschaft 21` |
| Scanner | **i2S SupraScan Quartz A1** |
| Scanning software | `multidotscan Vers. 2.1.11.60` |
| Scan date | **2025-03-05** |
| Resolution | **300 dpi**, 24-bit RGB |
| Compression | TIFF LZW |
| Approximate pixel dimensions | 9,900–10,100 × 4,300–4,400 px |
| File size | 66–115 MB per TIFF; about 2.5 GB total |

The immediate source files are in `/Users/mac/Downloads` and are named:

```
Bay_Landesamt_fuer_Wasserwirtschaft_210012.tif
...
Bay_Landesamt_fuer_Wasserwirtschaft_210089.tif
```

The 26 TIFFs comprise the annual chart plates, at least one near-blank verso or duplicate plate (`210014`), and several *Bemerkungen* (“remarks”) pages that contain technical instructions rather than charts. The tiles in this folder are derived from the chart plates. The remarks pages and blank plates were not tiled.

A separate file, `infos_historische_pegelstandsmessung_deutsches_museum.docx`, is correspondence from **Florian Preiß**, librarian at the **Deutsches Museum**, with bibliographic leads on historical water-level measurement. It is useful context and should be cited as background, but it is **not** a dataset datasheet and does not document these charts.

**Rights:** the TIFF copyright tag reads `(c)Bayerisches Hauptstaatsarchiv`. The JPEG tiles inherit that provenance. No licence, permission, or redistribution statement accompanies the tiles. Clarify rights with the archive before publishing or redistributing the images.

---

## 4. Inventory

### 4.1 Top-level folders

| Folder | Files | Years | Notes |
|---|---:|---|---|
| `tiles_1_1835-1837_plus_code/tiles` | 36 | 1835, 1836, 1837 | Also contains the generation code and metadata |
| `tiles` | 36 | 1839, 1845, 1848 | |
| `tiles 2` | 24 | 1849, 1850 | |
| `tiles 3` | 24 | 1849, 1850 | **Byte-identical duplicate of `tiles 2`** |
| `tiles 4` | 24 | 1862, 1863 | |
| `tiles 5` | 36 | 1864, 1865, 1872 | |
| `tiles 6` | 24 | 1873, 1877 | |
| `tiles 7` | 24 | 1878, 1883 | |
| `tiles 8` | 36 | 1890, 1891, 1893 | |
| **Total** | **264** | **20 years** | **240 unique, 24 redundant** |

All tile files are **744 × 3000 px**, RGB JPEG, approximately 0.49–0.91 MB each. The documented generation code saves at JPEG quality 90.

### 4.2 Duplicates

The only exact duplicate group is:

- `tiles 2/1849_*.jpg` ↔ `tiles 3/1849_*.jpg` (12 files)
- `tiles 2/1850_*.jpg` ↔ `tiles 3/1850_*.jpg` (12 files)

That is **24 redundant files**, about **13 MB**, with no metadata difference. One of the two folders should be removed or converted to a symlink before any split is created.

### 4.3 File naming

```
<year>_<month-number>_<English-month-abbreviation>.jpg
```

Examples: `1835_01_Jan.jpg`, `1893_12_Dec.jpg`.

The convention is machine-readable and consistent, but it encodes no station, scan ID, form, or version. Folder names contain spaces (`tiles 2`), and the duplicate folder makes path-based ingestion fragile.

---

## 5. Temporal coverage

### 5.1 Covered years

Every included year has all 12 months. There are no partial years inside the selected set.

| Year | Tiles | Metadata | Station | Form / note |
|---:|---:|---|---|---|
| 1835 | 12 | Yes | Ulm | 1830s–50s form |
| 1836 | 12 | Yes | Ulm | 1830s–50s form |
| 1837 | 12 | Yes | Ulm | **Apr–Sep from a pasted sheet**, hand-checked boxes |
| 1839 | 12 | Yes | Ulm | 1830s–50s form |
| 1845 | 12 | Yes | **Ulm → Neu-Ulm** | Q1–Q2 Ulm, Q3–Q4 Neu-Ulm |
| 1848 | 12 | Yes | Neu-Ulm | 1830s–50s form |
| 1849 | 12 | Yes | Neu-Ulm | 1830s–50s form |
| 1850 | 12 | Yes | Neu-Ulm | 1830s–50s form |
| 1862 | 12 | Yes | Neu-Ulm | 1862–63 form |
| 1863 | 12 | Yes | Neu-Ulm | 1862–63 form |
| 1864 | 12 | **No** | presumed Neu-Ulm | later form |
| 1865 | 12 | **No** | presumed Neu-Ulm | later form |
| 1872 | 12 | **No** | presumed Neu-Ulm | **16 px stage rulings** |
| 1873 | 12 | **No** | presumed Neu-Ulm | **16 px stage rulings** |
| 1877 | 12 | **No** | presumed Neu-Ulm | **16 px stage rulings** |
| 1878 | 12 | **No** | presumed Neu-Ulm | **16 px stage rulings** |
| 1883 | 12 | **No** | presumed Neu-Ulm | later form |
| 1890 | 12 | **No** | presumed Neu-Ulm | later form |
| 1891 | 12 | **No** | presumed Neu-Ulm | later form |
| 1893 | 12 | **No** | presumed Neu-Ulm | later form |

**Total:** 240 unique monthly tiles; 120 with metadata, 120 without.

### 5.2 Missing years

The selected years are not continuous. Between 1835 and 1893, the following years are absent:

```
1838
1840–1844
1846–1847
1851–1861
1866–1871
1874–1876
1879–1882
1884–1889
1892
```

That is **39 missing years** out of the 59-year span. The selection is almost certainly governed by archival survival, scanning priorities, or the condition of the bound volumes, not by hydrology. Any trend analysis must account for this selection before drawing climatic conclusions.

### 5.3 Station discontinuity

The station name changes within the record:

- **1835–1839:** Ulm.
- **1845:** Ulm for January–June; Neu-Ulm for July–December.
- **1848 onward:** Neu-Ulm.

Ulm and Neu-Ulm are neighbouring towns on opposite sides of the Danube. The change may reflect a new gauge location, a new gauge zero, a political/administrative boundary, or a combination. The dataset contains no datum, no gauge-zero elevation, and no station coordinates. **The two station epochs cannot be assumed to be on the same datum.** Any combined series must either:

1. model a station/epoch offset, or
2. publish the two epochs as separate series until archival research establishes the relationship.

---

## 6. Anatomy of a monthly tile

```
       day 1                                               day 31
         |                                                   |
         v                                                   v
       +-----------------------------------------------------+  ^
       |  vertical rules: one per day (~24 px)               |  |
       |  horizontal rules: stage increments                 |  |
       |                                                     |  stage
       |                                                     |  increases
       |            blue hand-drawn stage curve              |  upward
       |            (normally in the lower part)             |  |
       |                                                     |  |
       +-----------------------------------------------------+  v
         ^                                                   ^
         |                                                   |
      left crop edge                                  right crop edge
      (day labels below the plot are cropped away)
```

### 6.1 Geometry

| Property | Observation |
|---|---|
| Tile size | 744 × 3000 px |
| Horizontal axis | day of month, left to right, about **24 px/day** |
| Vertical axis | gauge stage, bottom to top |
| Grid | square, minor cell about **24 × 24 px** in most years |
| Major grid | thicker rule about every **5 minor cells** |
| Stage-ruling spacing | **16 px** in 1872–1878, **23–24 px** elsewhere |
| Day strip | cropped away; day numbers are not in the tile |
| Side scale | occasionally retained along an edge, especially 1865-03; it is a stage scale, not a day scale |
| Curves | blue ink, typically low on the page because the chart reserves large headroom for floods |
| Wash | light blue wash often accompanies the line |
| Red ink | substantial only in August 1835 |

The **horizontal** reading is the day; the **vertical** reading is the stage. The page is portrait because the plotted stage range is much taller than one month is wide, not because the chart is rotated. The original annual sheet is landscape, with twelve monthly columns side by side.

### 6.2 Why the curve is usually near the bottom

The chart reserves most of its vertical height for floods. Ordinary low water sits in the bottom fifth or quarter of the sheet. A curve near the bottom is therefore normal, not a cropping error and not necessarily a data gap. Conversely, a curve that climbs high is a real high-water event. The absence of a curve over part of a month may be a genuine observational gap, an ice period, a damaged sheet, or a faint ink trace; the dataset has no per-tile completeness flag.

### 6.3 Grid and ink

The printed grid is dark and can be mistaken for the curve. The curve is distinguished mainly by hue, thickness, and continuity:

- Blue ink: the dominant series.
- Blue wash: broad, low-saturation regions around the line; can merge with the line.
- Black grid: straight, regular, full-width or full-height.
- Red ink: rare; a second series or annotation.
- Show-through: faint mirror writing or curves from the verso, visible in some early scans.

In the oldest years the blue is faded enough that a conservative blue-colour threshold detects almost none of it. The curve is visible to a human but not reliably separable by colour alone. A colour-deconvolution or learned segmentation approach is required.

### 6.4 Resolution and precision

At 744 px per month, the horizontal resolution is about **1 px per hour** (744 px / 31 days / 24 hours). A 2–4 px line therefore represents several hours of timing uncertainty. Sub-daily peaks may be drawn as small circles or kinks, but the raster is marginal for hourly reconstruction. Vertical precision depends on the unknown stage unit represented by one 24 px grid cell; without the source scale, it cannot be converted to centimetres.

---

## 7. From annual sheet to monthly tile

The documented pipeline is a small computer-vision system, not a manual crop.

### 7.1 Detection (`pipeline.py`)

1. **Downsample the full sheet** to 3000 px wide for detection.
2. **Estimate skew separately** for the left and right halves by rotating through ±2° and maximising the variance of the row-profile derivative.
3. **Deskew each half** around its own centre.
4. For each of four quarter-panels, **fit four vertical month-separator lines** at a spacing of 214–226 px in preview coordinates, using column median darkness and a four-line comb.
5. **Detect the top of the plot** as the first strong ruling with a dense vertical grid below it.
6. **Detect the baseline** as the top line of the printed day strip: a triple of rulings 12–18 px and 25–36 px apart, with dense grid above and a sparse day-number row below.
7. **Check spread consistency:** if one panel’s top or base deviates by more than 12 px from the median of the four panels, and at least three panels agree, repair the outlier within ±12 px.
8. Write boxes and flags to `boxes_pipeline.json` and diagnostic overlays to `pbox*.png`.

### 7.2 Warping and tiling (`warp_all.py`)

1. Load the full-resolution TIFF and the detected boxes.
2. Apply the per-half deskew at full resolution.
3. For each panel and each of its three months, crop the month column between the fitted separators and between the detected top and baseline.
4. Resize the crop to **744 × 3000**.
5. For the six pasted 1837 months, use **hand-checked boxes** from `boxes3.json` instead of the automatic boxes; preserve the vertical scale by padding with grey `(232, 232, 232)` rather than stretching.
6. Save as `<year>_<month>_<Mon>.jpg` at quality 90.
7. Write `month_boxes.json` with scan ID, year, month, gauge, form, deskew angle, full-resolution box, and flags.

### 7.3 Metadata inputs

- **`priors.json`** — rough x positions of the four panel boundaries for each of the ten 1835–1863 scans. These are seeds for detection, not authoritative boxes.
- **`boxes_pipeline.json`** — the detection output: preview shape, per-half skew and centres, and four panel boxes with top/base and flags.
- **`month_boxes.json`** — 120 per-month records used to generate the tiles.
- **`boxes3.json`** — required by `warp_all.py` but **not present in this folder**. Without it, the 1837 pasted-sheet branch cannot be reproduced exactly.

### 7.4 Reproducibility problems in the code

- The full-size TIFF path is hard-coded as `/mnt/user-data/uploads/Bay_Landesamt_fuer_Wasserwirtschaft_<id>.tif`; it does not match the local `/Users/mac/Downloads` layout.
- The detector depends on `_small.npy` preview files that are not included.
- `boxes3.json` is missing.
- `warp_all.py` hard-codes a ten-scan `META` dictionary and therefore cannot regenerate the 1864–1893 tiles that are present in the folders.
- The code uses OpenCV and NumPy; no environment file or pinned versions are supplied.
- There is no test, checksum, or manifest that proves the 240 tiles were generated from the 26 TIFFs.

The pipeline is therefore **documented but not runnable as shipped**. The tiles are best treated as derived artifacts with an incomplete audit trail.

---

## 8. Metadata reference

### 8.1 `month_boxes.json` (120 records)

Each record:

```json
{
  "scan": "210012",
  "year": 1835,
  "month": 1,
  "gauge": "Ulm",
  "form": "1830s-50s form",
  "deskew_deg": 0.2,
  "box_px_fullres_after_deskew": [481, 812, 1220, 3828],
  "flags": []
}
```

| Field | Meaning | Limitation |
|---|---|---|
| `scan` | TIFF scan identifier | Only for 1835–1863 |
| `year`, `month` | Calendar assignment | No day precision; month start is assumed |
| `gauge` | `Ulm` or `Neu-Ulm` | No station coordinates or datum |
| `form` | Chart layout label | Only three values; later forms absent |
| `deskew_deg` | Applied rotation | Per half-page, not per month |
| `box_px_fullres_after_deskew` | Crop coordinates | Full-resolution pixels, not preview pixels |
| `flags` | Detection warnings | Free text; no controlled vocabulary |

The 18 flagged records are:

- **1837:** all 12 months have top/base deviations because of the pasted sheet. Six months (April–September) are explicitly marked `"hand-checked box (pasted sheet)"`.
- **1845:** October–December have a repaired base (`1018 → 1132`, a 114 px correction).
- **1848:** January–March have a repaired base (`1098 → 1132`, a 38 px correction).

A 114 px repair is large enough to change the vertical extent of a tile by several percent. These should be visually re-checked against the TIFFs before use.

### 8.2 Coverage gaps in the metadata

- No metadata for **1864, 1865, 1872, 1873, 1877, 1878, 1883, 1890, 1891, 1893** (120 tiles).
- No per-tile curve mask, curve coordinates, or numeric values.
- No unit, scale, datum, or station geometry.
- No source-scan mapping for the later tiles.
- No licence, checksum, or generation timestamp.
- No month length (`28/29/30/31`) or day-axis origin.
- No explicit flag for “curve complete”, “curve partial”, “ice-affected”, or “red series present”.

### 8.3 Box statistics

| Property | Range |
|---|---|
| Crop height, full resolution | 2,772–3,031 px |
| Crop width, full resolution | 713–755 px |
| Deskew angle | −0.95° to +1.05° |
| Records with flags | 18 / 120 |
| Pasted-sheet records | 6 / 120 |

Because every crop is resized to 744 × 3000, the source pixels per day and pixels per stage unit vary slightly from year to year. The 1837 pasted months are padded rather than stretched, so their scale differs from the other tiles.

---

## 9. Quantitative audit

### 9.1 Per-year image and ink statistics

The “blue %” column uses a conservative blue-colour threshold. A value of `0.0` means the curve was not detected by that threshold, **not** that no curve exists. “Dark ink %” includes the grid, text, borders, and curve, so it is an indicator of overall print density, not curve coverage.

| Year | Tiles | Blue % | Dark ink % | Grid x / y (px) |
|---:|---:|---:|---:|---:|
| 1835 | 12 | 0.00 | 7.9 | 24 / 24 |
| 1836 | 12 | 0.00 | 9.5 | 24 / 24 |
| 1837 | 12 | 0.10 | 7.4 | 24 / 24 |
| 1839 | 12 | 0.00 | 5.8 | 24 / 24 |
| 1845 | 12 | 0.10 | 4.4 | 24 / 24 |
| 1848 | 12 | 0.10 | 5.5 | 24 / 24 |
| 1849 | 12 | 0.20 | 5.0 | 24 / 24 |
| 1850 | 12 | 0.10 | 4.4 | 24 / 24 |
| 1862 | 12 | 0.10 | 17.5 | 23 / 24 |
| 1863 | 12 | 0.20 | 13.8 | 24 / 23 |
| 1864 | 12 | 0.10 | 12.6 | 24 / 23 |
| 1865 | 12 | 0.10 | 4.9 | 23 / 23 |
| 1872 | 12 | 0.50 | 11.6 | 24 / **16** |
| 1873 | 12 | 0.50 | 10.9 | 24 / **16** |
| 1877 | 12 | 0.20 | 15.6 | 23 / **16** |
| 1878 | 12 | 0.10 | 14.7 | 24 / **16** |
| 1883 | 12 | 0.30 | 12.8 | 24 / 23 |
| 1890 | 12 | 0.20 | 13.9 | 23 / 23 |
| 1891 | 12 | 0.40 | 14.1 | 23 / 23 |
| 1893 | 12 | 0.30 | 12.7 | 24 / 23 |

### 9.2 What the audit establishes

1. **The corpus is visually heterogeneous across eras.** Grid spacing, ink density, paper tone, and chart form change several times.
2. **Colour-based curve extraction will fail on the oldest years.** The blue signal is too weak in 1835–1839 for a naive threshold. A model trained on 1890s blue ink will not transfer directly to 1830s faded ink.
3. **1872–1878 is a separate domain.** The stage-ruling spacing drops from about 24 px to 16 px, meaning either a finer paper grid, a different stage scale, or both. Any pixel-to-stage calibration must be per form, not global.
4. **1862–1864 is unusually dark.** Dark-ink fractions of 13–18% suggest denser print, heavier scan contrast, or both.
5. **The red series is exceptional.** Only August 1835 has a substantial red trace. It is invisible to a blue-ink pipeline and absent from the metadata.
6. **There is no evidence of a single consistent “dataset generation event” for all years.** The metadata, code, and forms cover 1835–1863; the later folders are tiled but undocumented.

---

## 10. Critical examination

### 10.1 Strengths

- **Historical rarity.** Continuous monthly gauge charts from the 1830s–1890s are uncommon, and a run of 20 years is a meaningful record for pre-instrumental hydrology.
- **High-quality source scans.** 300 dpi, 24-bit colour, archival TIFFs with documented scanner and holding institution.
- **Consistent monthly unit.** One image per month makes the corpus easy to index, visualise, and split.
- **Human-verified special cases.** The 1837 pasted sheet, the 1845 and 1848 base repairs, and the per-half deskew show real care.
- **Multiple chart forms.** The corpus is a natural benchmark for domain shift across paper, grid, ink, and layout.
- **A clear conceptual bridge.** The charts connect document-image analysis, historical metrology, and climate/hydrology.

### 10.2 Weaknesses and risks

| # | Issue | Evidence | Consequence | Required action |
|---:|---|---|---|---|
| 1 | It is an image corpus, not a numeric dataset | Tiles contain only grid and ink; no values | Cannot be used directly for statistics or model regression | Extract curves and calibrate, or rename it an image corpus |
| 2 | Half the tiles lack metadata | 120 records for 240 tiles | 1864–1893 cannot be traced to a scan, station, or form | Rebuild metadata from TIFFs |
| 3 | No labels, units, or datum | Titles and scales are outside the crop | Absolute stage is unknowable from a tile alone | Transcribe headers and calibrate per form/era |
| 4 | Station discontinuity | Ulm → Neu-Ulm in 1845 | A single combined series may mix datums | Define station epochs; model offsets |
| 5 | Duplicate folder | `tiles 2` = `tiles 3` | Inflated counts; leakage in random splits | Remove one copy; hash the manifest |
| 6 | Inconsistent scale after normalisation | Crop heights 2,772–3,031 px; widths 713–755 px; 16 px grid in 1872–78 | Same pixel displacement means different stage change | Store affine transform and grid calibration per tile |
| 7 | 1837 pasted sheet is a special case | Six months padded, not stretched; hand boxes | Vertical scale and borders differ from neighbours | Flag and exclude from naive comparisons |
| 8 | Faded ink in early years | Blue threshold detects ~0% in 1835–36 | Colour segmentation is biased by era | Use colour deconvolution, contrast enhancement, or learned segmentation |
| 9 | Red series is unexplained | 4,232 red px in Aug 1835 only | A second variable may be silently ignored | Research the source legend; label or mask it |
| 10 | No ground truth or split | No masks, no values, no train/val/test | No reproducible benchmark | Create a gold set and year-based splits |
| 11 | Domain shift across forms | Grid 24→16→23 px; dark ink 4→18% | Random splits overestimate generalisation | Split by year/form; report per-era metrics |
| 12 | Pipeline is not reproducible | Hard-coded `/mnt` path, missing `.npy` and `boxes3.json` | Tiles cannot be regenerated or audited | Publish inputs, code, environment, checksums |
| 13 | Rights unclear | TIFF copyright tag only | Redistribution may be restricted | Obtain archive permission and state licence |
| 14 | Selection bias | 20 of 59 years, non-random gaps | Trend estimates may be biased | Document selection; avoid naive climatology |
| 15 | Possible show-through and edge artefacts | Faint verso traces; page edges in some tiles | False curves and border contamination | Mask borders; flag ghost ink |
| 16 | No day-strip or month-start verification | Day labels cropped; day 1 assumed at left | Day alignment may be off by one or more | Verify against TIFFs; store day origin |
| 17 | No per-tile completeness flag | Some curves may be partial or faint | Missing data may be read as low stage | Manual audit; add coverage metadata |
| 18 | Name/content mismatch | “ICE LEVEL” but charts are water level | Users may expect ice observations | Rename or document the name explicitly |

### 10.3 The most dangerous misunderstandings

1. **“The curve is the water level in pixels.”** It is, but without the vertical scale and datum it is only a shape. A model can learn shape; a scientist cannot report centimetres.
2. **“All tiles are comparable because they are 744 × 3000.”** Normalisation removed the original scale differences. Equal pixel height does not mean equal stage range.
3. **“Ulm and Neu-Ulm are the same station.”** They are different names, possibly different gauges and datums. Treating them as one series is a scientific assumption, not a fact.
4. **“The blue curve is always the only series.”** August 1835 has a red series; other sheets may have annotations, corrections, or ice marks.
5. **“Missing curve means zero.”** A blank area may be missing observation, ice cover, faint ink, damage, or a crop error.
6. **“The folder name tells us the variable.”** It does not. The charts are water-level charts.

---

## 11. Concepts and ideas

### 11.1 The underlying concept: data rescue from paper charts

Before digital sensors, hydrological services recorded water levels on printed graph paper. The result is a large body of “dark data”: images that are readable by humans but invisible to analysis. This dataset is a small, well-preserved slice of that world. Its real value is as a **data-rescue corpus**: a place to develop and test methods for turning hand-drawn environmental records into usable time series.

The conceptual chain is:

```
archival bound volume
  → annual chart sheet
  → monthly graph-paper column
  → hand-drawn ink curve
  → digitised raster tile
  → segmented curve
  → calibrated stage values
  → quality-controlled time series
  → hydrological / climatic interpretation
```

The current dataset sits at step 4. Most of the work, and most of the scientific value, lies in steps 5–8.

### 11.2 Historical hydrology and climate

Potential questions, subject to the caveats above:

- What was the seasonal water-level regime of the upper Danube in the 1830s–1890s?
- How frequent and severe were floods and droughts before modern gauging?
- Did the timing of snowmelt and low-water seasons shift over the century?
- How do the historical charts compare with modern Neu-Ulm records?
- Can known historical events (floods, ice jams, severe winters) be identified in the curves?
- How did the move from Ulm to Neu-Ulm affect the recorded levels?
- What does the red August 1835 series represent?
- Are there multi-year wet/dry cycles in the pre-instrumental record?
- How did river regulation and embankment construction change the stage regime?
- What uncertainty does hand-drawing introduce into extreme-value estimates?

These are legitimate research directions, but only after station, datum, and calibration work.

### 11.3 Document-image analysis and chart understanding

The corpus supports methodological research on:

- **Layout analysis** of historical tables with repeated monthly columns.
- **Deskew and dewarping** of bound-volume scans with page curvature.
- **Grid removal** and separation of printed rules from hand-drawn ink.
- **Colour deconvolution** of blue ink, blue wash, black grid, red annotations, and paper tone.
- **Curve tracing** through gaps, crossings, wash, and faded ink.
- **Calibration** from grid spacing and printed scales.
- **Handwritten text recognition** of headers, dates, station names, and remarks.
- **Domain adaptation** across 1830s, 1860s, 1870s, and 1890s forms.
- **Uncertainty estimation** for hand-drawn environmental data.
- **Human-in-the-loop** digitisation workflows.

### 11.4 Benchmark design

A well-designed benchmark would not ask “predict the water level from this JPEG” without context. It would define tasks such as:

1. **Month/year classification** from a tile (easy; tests metadata leakage).
2. **Form/era classification** (1830s–50s, 1862–63, 1870s fine grid, 1880s–90s).
3. **Curve segmentation** (pixel mask for the blue line, excluding grid and wash).
4. **Grid calibration** (predict pixels per day and pixels per stage unit).
5. **Stage regression** (predict relative stage at each day, in grid units).
6. **Absolute stage regression** (only after units and datum are transcribed).
7. **Gap detection** (distinguish missing curve from low stage).
8. **Red-series detection** (find the rare second ink).
9. **Station classification** (Ulm vs Neu-Ulm).
10. **Header transcription** (year, station, form, remarks).

The hardest and most valuable task is **absolute stage regression with uncertainty**, because it requires calibration and historical metrology, not just image segmentation.

### 11.5 FAIR and datasheet thinking

Measured against the FAIR principles:

- **Findable:** partially. File names encode year and month, but folders are inconsistent and the archive IDs are not in the tile names.
- **Accessible:** locally yes; no public identifier or licence.
- **Interoperable:** no schema, no units, no controlled vocabulary.
- **Reusable:** limited by missing metadata, unclear rights, and non-runnable code.

A proper datasheet should document motivation, composition, collection, preprocessing, uses, distribution, maintenance, and ethical/legal constraints. This document is a first step toward that datasheet, not a substitute for it.

---

## 12. What this dataset is not

- It is **not** a ready-to-use time series.
- It is **not** a table of daily values.
- It is **not** an ice-observation dataset, despite the folder name.
- It is **not** a complete 1835–1893 record.
- It is **not** calibrated in centimetres or metres.
- It is **not** station-consistent across the whole period.
- It is **not** labelled for curve completeness, ice, gaps, or red ink.
- It is **not** split into train/validation/test sets.
- It is **not** licence-cleared for redistribution.
- It is **not** reproducible from the code and files as currently shipped.

---

## 13. Recommended remediation plan

### P0 — before any modelling or publication

1. **Freeze a canonical manifest.** One row per unique tile with SHA-256, dimensions, source scan ID, year, month, folder, and duplicate status. Remove `tiles 3` or mark it as a mirror.
2. **Re-crop from the TIFFs.** Keep the raw full-resolution crop, the affine transform, and the exact box. Do not rely only on the resized JPEG.
3. **Transcribe the headers for all 20 years.** Record station, year, form, month names, units, and any remarks. This closes the 1864–1893 metadata gap.
4. **Establish station epochs and datum.** Research the Ulm → Neu-Ulm move. Record gauge-zero elevation, coordinates, and any changes. Do not combine epochs until this is resolved.
5. **Calibrate the grid.** For each form/era, measure pixels per day, pixels per minor stage unit, and the printed scale. Record the unit and the conversion to metres.
6. **Audit curve completeness.** Manually inspect all 240 tiles (or a stratified sample) for missing curve, faint ink, show-through, edge artefacts, and red ink. Add a controlled flag set.
7. **Build a small gold set.** At least 24 months, stratified across eras, with hand-traced curve masks and daily stage values in grid units. This is the seed for any benchmark.
8. **Resolve rights.** Obtain written permission or a licence statement from the Bayerisches Hauptstaatsarchiv.

### P1 — make it usable

9. **Create a canonical metadata schema** (Section 14).
10. **Publish curve masks and extracted series**, not only JPEGs.
11. **Split by year and form**, never by random tile. Report per-era metrics.
12. **Document the red series.** Find the source legend or annotate it as unknown.
13. **Run HTR/OCR on headers and remarks** to recover station, year, units, and technical notes.
14. **Produce a proper datasheet** with motivation, composition, collection, preprocessing, uses, distribution, maintenance, and legal terms.
15. **Fix the pipeline.** Remove hard-coded paths; include `_small.npy`, `boxes3.json`, environment pins, and a regeneration test.

### P2 — extend the science

16. **Digitise daily (and, where possible, sub-daily) stage values** with uncertainty intervals.
17. **Harmonise the station epochs** and compare with modern Neu-Ulm data.
18. **Analyse extremes, seasonality, and trends**, with explicit treatment of missing years.
19. **Investigate ice-related annotations** and the August 1835 red series.
20. **Publish a benchmark paper** with baselines for segmentation, calibration, and regression.

---

## 14. Proposed canonical metadata schema

A single JSON record per tile, with no field left implicit:

```json
{
  "tile_id": "1835-01-ulm-v1",
  "file": "tiles_1_1835-1837_plus_code/tiles/1835_01_Jan.jpg",
  "sha256": "...",
  "source": {
    "archive": "Bayerisches Hauptstaatsarchiv",
    "series": "Bayer. Landesamt fuer Wasserwirtschaft 21",
    "scan_id": "210012",
    "tiff_file": "Bay_Landesamt_fuer_Wasserwirtschaft_210012.tif",
    "scan_date": "2025-03-05",
    "scanner": "i2S SupraScan Quartz A1",
    "dpi": 300,
    "rights": "© Bayerisches Hauptstaatsarchiv; permission required"
  },
  "time": {
    "year": 1835,
    "month": 1,
    "days_in_month": 31,
    "day_1_x_px": 0,
    "px_per_day": 24.0,
    "time_direction": "left_to_right"
  },
  "station": {
    "name": "Ulm",
    "epoch": "1835-1845H1",
    "coordinates": null,
    "gauge_zero_m": null,
    "datum_note": "unknown; must be established from archival sources"
  },
  "chart": {
    "form": "1830s-50s",
    "grid_px_x": 24.0,
    "grid_px_y": 24.0,
    "stage_direction": "bottom_to_top",
    "stage_unit": "unknown",
    "minor_unit_m": null,
    "major_every": 5,
    "side_scale_visible": false,
    "day_strip_included": false
  },
  "crop": {
    "box_fullres_after_deskew": [481, 812, 1220, 3828],
    "deskew_deg": 0.2,
    "resize_to": [744, 3000],
    "padding": null,
    "pasted_sheet": false
  },
  "curve": {
    "blue_present": true,
    "blue_mask": null,
    "red_present": false,
    "wash_present": true,
    "completeness": "unknown",
    "extraction_method": null,
    "values_csv": null
  },
  "quality": {
    "flags": [],
    "ghost_ink": "possible",
    "edge_artefact": "none",
    "manual_review": false
  },
  "provenance": {
    "generated_by": "warp_all.py",
    "generated_at": null,
    "pipeline_version": "unknown",
    "notes": ""
  }
}
```

The key additions over the current metadata are: **checksum, explicit time geometry, station epoch, datum, units, calibration, curve masks, completeness, rights, and provenance**. Without these, the dataset remains an image collection rather than a scientific dataset.

---

## 15. Suggested benchmark protocol

### 15.1 Splits

- **Temporal split:** train on 1835–1865, validate on 1872–1878, test on 1883–1893. This tests era generalisation.
- **Form split:** hold out one chart form entirely.
- **Station split:** if enough data, train on Ulm and test on Neu-Ulm, or vice versa.
- **Never** split adjacent months randomly: they share paper, scan, lighting, and often the same curve.

### 15.2 Metrics

| Task | Metric |
|---|---|
| Curve segmentation | pixel IoU, Dice, boundary F1 |
| Grid removal | grid-pixel recall/precision |
| Relative stage regression | MAE in grid units; MAE in pixels |
| Absolute stage regression | MAE in cm or m, with uncertainty calibration |
| Peak detection | timing error in hours/days; peak-stage error |
| Gap detection | F1 for missing-curve intervals |
| Red-series detection | precision/recall on the rare class |
| Form/era classification | balanced accuracy |
| Header transcription | character/word error rate |

### 15.3 Baselines to report

- Naive threshold on blue channel.
- Colour deconvolution + morphological line removal.
- U-Net or similar segmentation model trained per era.
- Classical graph tracing with continuity constraints.
- Human expert tracing as the upper bound.

---

## 16. Licensing and citation

No licence file accompanies the dataset. The TIFF copyright tag identifies the **Bayerisches Hauptstaatsarchiv** as the rights holder. The JPEG tiles are derivative images. Before redistribution:

1. request permission from the archive,
2. record the permission in the dataset,
3. cite the archive series and scan IDs,
4. preserve the TIFF metadata,
5. distinguish the archival images from any new annotations or extracted values.

Suggested citation form (to be completed once rights are cleared):

> Bayerisches Hauptstaatsarchiv, series “Bayer. Landesamt für Wasserwirtschaft 21”, annual water-level tables for Ulm/Neu-Ulm, scan IDs 210012–210089, 300 dpi, 2025. Monthly tiles derived for the ICE LEVEL DATASET, 2026.

Also cite the Deutsches Museum correspondence (`infos_historische_pegelstandsmessung_deutsches_museum.docx`) only as bibliographic background, not as documentation of the charts.

---

## 17. Glossary

| Term | Meaning |
|---|---|
| **Pegel** | Gauge; a device or station for measuring water level |
| **Pegelnullpunkt** | Gauge zero; the reference level below which stage is normally not negative |
| **Wasserstand / Wasserhöhe** | Water level / water height |
| **Wasserhöhenmaß** | Water-level gauge or measuring scale |
| **Tabelle** | Table; the annual chart sheet is titled as a table |
| **Bemerkungen** | Remarks; the archival notes pages accompanying some charts |
| **Ulm** | German city on the Danube; the earlier gauge location |
| **Neu-Ulm** | Bavarian city opposite Ulm; the later gauge location |
| **Stage** | Water level relative to a fixed gauge zero |
| **Hydrograph** | A curve of stage or discharge over time |
| **Day strip** | The printed row of day numbers below the plot, cropped out of the tiles |
| **Deskew** | Rotation correction for a tilted scan |
| **Pasted sheet** | A sheet physically pasted into the volume; in 1837, April–September |
| **Form** | A chart layout/paper era (1830s–50s, 1862–63, 1870s fine grid, later) |

---

## 18. Quick fact sheet

| Fact | Value |
|---|---|
| Unique monthly tiles | **240** |
| Years covered | **20** (1835–1893, with gaps) |
| Missing years in span | **39** |
| Months per included year | **12** (complete) |
| JPEG files on disk | **264** |
| Duplicate files | **24** (`tiles 2` = `tiles 3`) |
| Tile dimensions | **744 × 3000 px**, RGB JPEG |
| Tile disk usage | **162 MB** |
| Full-resolution TIFFs | **26** files, about **2.5 GB** |
| TIFF resolution | **300 dpi**, 24-bit RGB, LZW |
| Scan date | **2025-03-05** |
| Holding institution | **Bayerisches Hauptstaatsarchiv** |
| Documented metadata | **120 tiles** (1835–1863) |
| Undocumented tiles | **120** (1864–1893) |
| Tile grid | 24 px minor cell; **16 px stage rulings in 1872–1878** |
| Substantial red ink | **August 1835 only** |
| Ground-truth values | **None** |
| Licence | **Unclear; archive rights apply** |

---

## 19. Bottom line

The ICE LEVEL DATASET is a **valuable but unfinished data-rescue corpus**. Its strongest asset is the archival source: a rare, high-resolution, multi-decade visual record of water levels on the upper Danube. Its weakest point is the gap between “image” and “data”: no units, no datum, no station history, no numeric values, no labels, and no rights statement.

The right next move is not to train a model on the JPEGs. It is to:

1. transcribe the headers and scales,
2. establish the station/datum history,
3. calibrate the grid,
4. hand-trace a small gold set,
5. then build the extraction and benchmark pipeline.

If those steps are taken, the corpus can become a genuinely useful benchmark for historical chart understanding and a scientific record of nineteenth-century Danube hydrology. If they are skipped, it remains a beautiful but opaque collection of graph paper.

---

## Appendix A — Web interface and reproducible build

A static, local-first browser lives in `dashboard/`. It turns the manifest, thumbnails, and pattern composites into a validity-aware interface. It does not add measurements, infer units, or modify the source images.

### A.1 Run it

```bash
cd "ICE LEVEL DATASET"
python3 dashboard/build_dashboard.py
python3 -m http.server 8000
# open http://localhost:8000/dashboard/
```

Opening `dashboard/index.html` directly works in most browsers, but a local HTTP server is safer for file links, exports, and browser storage.

### A.2 What the build produces

| Output | Meaning |
|---|---|
| `dashboard/data.js` | `window.ICE_DATA` with 240 tile records, year summaries, station epochs, constraints, and computed stats |
| `dashboard/manifest.json` | Full machine-readable catalogue |
| `dashboard/manifest.csv` | Flat catalogue for spreadsheet use |
| `dashboard/thumbs/` | 240 JPEG thumbnails, 124 × 500 px |
| `dashboard/patterns/year_YYYY.jpg` | 20 annual strips, January–December |
| `dashboard/patterns/overview.jpg` | 4 × 5 contact sheet of the 20 included years |
| `dashboard/patterns/long_run.jpg` | One 240-month horizontal visual sequence |
| `dashboard/index.html` | Interface markup |
| `dashboard/styles.css` | Archive-style visual system |
| `dashboard/app.js` | Views, filters, exports, modal, review workflow |

Rebuild is deterministic for the image derivatives and catalogue fields, except the `generated` date. The builder refuses to invent metadata for the 120 image-only tiles.

### A.3 Views

- **Overview** — critical distinction, eight headline statistics, year × month coverage matrix, station epochs, contact-sheet preview, documentation bars.
- **Long-run patterns** — 240-month strip, 20 × 12 calendar matrix with 104 px cells, annual strips with year metadata, detection-flag and metadata filters.
- **Query** — filter by year range, month, station, metadata, technical flag, review status, free text, and minimum completeness. Sort by year, completeness, blue ink, or red ink. Export the current result set as CSV or JSON. Every query is reproducible from its URL parameters.
- **Validity** — supported / conditional / unsupported verdicts, ten use cases, integrity checks, review progress, highest-risk records, downloadable validity report.
- **About** — provenance, rebuild command, data contract, limits.

### A.4 Query contract

Filters and exports use these fields:

`id`, `year`, `month`, `month_name`, `station`, `station_source`, `form`, `source_scan`, `source_status`, `doc_score`, `needs_review`, `duplicate`, `width`, `height`, `bytes`, `blue_pct`, `red_px`, `grid_x`, `grid_y`, `detection_flags`, `tech_flags`, `doc_gaps`, `review_status`, `review_updated`, `review_note`, `file`.

URL parameters are `year_from`, `year_to`, `month`, `station`, `metadata`, `flag`, `review`, `q`, `score`, and `sort`. Example:

```text
dashboard/?flag=pasted&sort=score-asc#query
```

Technical-flag values are `any`, `duplicate`, `faint`, `red`, `pasted`, `detection`, and `dimensions`. Review values are `unreviewed`, `looks-good`, `needs-review`, and `reject`.

### A.5 Human review is local

Reviews are stored in `localStorage` under `ice-reviews-v1`. They are not uploaded and not shared. Export them before changing browser or machine. A review records status, six visual checks, a free-text note, and an ISO timestamp. Clearing the browser profile deletes them.

The review helps catalogue uncertainty; it does not create ground truth. A “looks good” tile is still a picture without units or a datum.

### A.6 Validity behaviour

The interface computes descriptive statistics from the manifest only. It never claims that a curve is correct because its documentation score is high. The selection audit states what a filtered set supports and which caveats remain. The highest-risk queue deliberately samples distinct risk classes — pasted sheet, repaired base, faint ink, image-only low-completeness, red ink — rather than six near-identical rows.

Headline constraints remain visible throughout:

- 240 tiles, 20 years, **39 missing years**.
- 120 metadata-linked tiles; **120 image-only tiles**.
- **18 detection flags**, 50 faint-ink tiles, one substantial red-ink tile.
- Ulm → Neu-Ulm in **July 1845**, with no verified datum continuity.
- No units, gauge datum, station coordinates, extracted values, or licence.

### A.7 Verification performed

The interface was checked with headless Chrome and a Chrome DevTools Protocol script:

- 8 statistic cards, 240 coverage cells, 240 pattern cells, 240 query rows rendered.
- `flag=pasted` returned exactly 6 records; “Audit this selection” rendered the selection caveats.
- The modal opened April 1837 with 6 checklist rows and 13 metadata rows.
- A review saved to `localStorage`, survived reload, and appeared in the query result.
- The detection-flag filter reduced the pattern matrix to 18 visible cells.
- The risk queue sampled 1837, 1848, 1864, 1835, 1845, and 1865.
- No JavaScript exceptions or console errors were recorded.

### A.8 Known interface limits

- It is a catalogue of images, not a numeric database. There is no chart digitisation, curve extraction, unit inference, or datum reconstruction.
- Local reviews are single-browser state. There is no authentication, multi-user merge, or server backup.
- Pattern images are resized derivatives; use the original TIFFs or JPEG tiles for measurement work.
- The 4 × 5 overview and 104 px matrix cells are for navigation, not close reading. Open a record for the full tile.
- The validity report is a generated caution document, not a peer-reviewed assessment.
- Redistribution remains blocked until the archive confirms rights.

---

*End of document.*
