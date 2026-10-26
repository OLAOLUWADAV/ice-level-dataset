#!/usr/bin/env python3
"""Build the static ICE LEVEL dashboard: manifest, thumbnails, patterns, data.js."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import urllib.parse
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DASH = Path(__file__).resolve().parent
THUMBS = DASH / "thumbs"
PATTERNS = DASH / "patterns"
META_PATH = ROOT / "tiles_1_1835-1837_plus_code" / "month_boxes.json"

TILE_DIRS = [
    "tiles_1_1835-1837_plus_code/tiles",
    "tiles",
    "tiles 2",
    "tiles 4",
    "tiles 5",
    "tiles 6",
    "tiles 7",
    "tiles 8",
    "tiles 3",
]

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
EXPECTED = (744, 3000)
FIRST_YEAR, LAST_YEAR = 1835, 1893


def font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    return ImageFont.load_default()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def relative_url(path: Path) -> str:
    rel = Path("..") / path.relative_to(ROOT)
    return urllib.parse.quote(rel.as_posix(), safe="/")


def measure_tile(path: Path) -> dict:
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im).astype(np.int16)
    gray = np.asarray(im.convert("L")).astype(float)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    blue = (b - r > 6) & (b - g > 1) & (b > 60) & (r < 200)
    red = (r - g > 35) & (r - b > 35) & (r > 90) & (g < 150)
    dark = gray < 140

    def grid_spacing(profile: np.ndarray, lo: int = 12, hi: int = 40) -> int:
        sig = profile - profile.mean()
        ac = np.correlate(sig, sig, "full")[len(sig) - 1 :]
        segment = ac[lo:hi]
        return lo + int(np.argmax(segment)) if len(segment) else 0

    col_profile = np.median(gray, axis=0)
    row_profile = np.median(gray, axis=1)
    return {
        "width": im.width,
        "height": im.height,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "mean_luma": round(float(gray.mean()), 2),
        "dark_pct": round(float(dark.mean() * 100), 2),
        "blue_pct": round(float(blue.mean() * 100), 3),
        "red_px": int(red.sum()),
        "grid_x": int(grid_spacing(col_profile)),
        "grid_y": int(grid_spacing(row_profile)),
    }


def load_metadata() -> dict[tuple[int, int], dict]:
    records = json.loads(META_PATH.read_text())
    return {(int(r["year"]), int(r["month"])): r for r in records}


def collect_tiles() -> dict[tuple[int, int], dict]:
    groups: dict[tuple[int, int], list[Path]] = defaultdict(list)
    for d in TILE_DIRS:
        folder = ROOT / d
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.jpg")):
            m = re.match(r"^(\d{4})_(\d{2})_([A-Z][a-z]{2})\.jpg$", p.name)
            if not m:
                continue
            groups[(int(m.group(1)), int(m.group(2)))].append(p)
    return groups


def station_for(year: int, month: int, meta: dict | None) -> tuple[str, str]:
    if meta and meta.get("gauge"):
        return meta["gauge"], "metadata"
    if year == 1845:
        return ("Ulm" if month <= 6 else "Neu-Ulm"), "inferred"
    if year < 1845:
        return "Ulm", "inferred"
    return "Neu-Ulm", "inferred"


def score_tile(meta: dict | None, source_scan: str | None, station_source: str,
               form: str, duplicate: bool, dimensions_ok: bool, blue_pct: float,
               detection_flags: list[str]) -> int:
    score = 0
    score += 30 if meta else 0
    score += 15 if source_scan else 0
    score += 10 if meta and not detection_flags else 0
    score += 10 if not duplicate else 0
    score += 10 if dimensions_ok else 0
    score += 10 if station_source == "metadata" else 0
    score += 5 if form and form != "unclassified" else 0
    score += 10 if blue_pct >= 0.05 else 0
    return min(score, 100)


def build_manifest() -> dict:
    metadata = load_metadata()
    groups = collect_tiles()
    tiles = []

    for (year, month) in sorted(groups):
        paths = groups[(year, month)]
        canonical = paths[0]
        meta = metadata.get((year, month))
        source_scan = str(meta["scan"]) if meta and meta.get("scan") else None
        detection_flags = list(meta.get("flags", [])) if meta else []
        station, station_source = station_for(year, month, meta)
        form = meta["form"] if meta and meta.get("form") else "unclassified"
        duplicate = len(paths) > 1
        metrics = measure_tile(canonical)
        dimensions_ok = (metrics["width"], metrics["height"]) == EXPECTED

        doc_gaps = []
        if not meta:
            doc_gaps.append("No per-tile metadata")
        if not source_scan:
            doc_gaps.append("Source scan not linked")
        if station_source != "metadata":
            doc_gaps.append("Station inferred")
        if form == "unclassified":
            doc_gaps.append("Form unclassified")

        tech_flags = []
        if duplicate:
            tech_flags.append("Duplicate file")
        if detection_flags:
            tech_flags.append("Detection flags")
        if metrics["blue_pct"] < 0.05:
            tech_flags.append("Faint blue ink")
        if metrics["red_px"] > 200:
            tech_flags.append("Red ink present")
        if not dimensions_ok:
            tech_flags.append("Unexpected dimensions")
        if any("pasted" in f for f in detection_flags):
            tech_flags.append("Pasted sheet")

        score = score_tile(meta, source_scan, station_source, form, duplicate,
                           dimensions_ok, metrics["blue_pct"], detection_flags)

        tiles.append({
            "id": f"{year}-{month:02d}",
            "year": year,
            "month": month,
            "month_name": MONTHS[month - 1],
            "day_label": f"{year}-{month:02d}-01",
            "file": relative_url(canonical),
            "files": [relative_url(p) for p in paths],
            "duplicate": duplicate,
            **metrics,
            "dimensions_ok": dimensions_ok,
            "station": station,
            "station_source": station_source,
            "form": form,
            "form_source": "metadata" if meta and meta.get("form") else "unclassified",
            "source_scan": source_scan,
            "source_status": "linked" if source_scan else "unlinked",
            "meta": {
                "scan": str(meta["scan"]),
                "gauge": meta.get("gauge"),
                "form": meta.get("form"),
                "deskew_deg": meta.get("deskew_deg"),
                "box": meta.get("box_px_fullres_after_deskew"),
                "flags": list(meta.get("flags", [])),
            } if meta else None,
            "detection_flags": detection_flags,
            "doc_gaps": doc_gaps,
            "tech_flags": tech_flags,
            "needs_review": bool(doc_gaps or tech_flags),
            "doc_score": score,
        })

    years_present = sorted({t["year"] for t in tiles})
    missing_years = [y for y in range(FIRST_YEAR, LAST_YEAR + 1) if y not in years_present]
    year_summary = []
    for year in years_present:
        group = [t for t in tiles if t["year"] == year]
        year_summary.append({
            "year": year,
            "months": len(group),
            "metadata": sum(1 for t in group if t["meta"]),
            "linked": sum(1 for t in group if t["source_scan"]),
            "flagged": sum(1 for t in group if t["detection_flags"]),
            "duplicates": sum(1 for t in group if t["duplicate"]),
            "avg_score": round(sum(t["doc_score"] for t in group) / len(group), 1),
        })

    all_files = sum(len(t["files"]) for t in tiles)
    stats = {
        "generated": date.today().isoformat(),
        "unique_tiles": len(tiles),
        "files_on_disk": all_files,
        "duplicate_files": all_files - len(tiles),
        "duplicate_tiles": sum(1 for t in tiles if t["duplicate"]),
        "years": len(years_present),
        "years_present": years_present,
        "missing_years": missing_years,
        "missing_year_count": len(missing_years),
        "metadata_tiles": sum(1 for t in tiles if t["meta"]),
        "linked_tiles": sum(1 for t in tiles if t["source_scan"]),
        "station_explicit": sum(1 for t in tiles if t["station_source"] == "metadata"),
        "form_classified": sum(1 for t in tiles if t["form"] != "unclassified"),
        "review_tiles": sum(1 for t in tiles if t["needs_review"]),
        "avg_doc_score": round(sum(t["doc_score"] for t in tiles) / len(tiles), 1),
        "red_tiles": sum(1 for t in tiles if t["red_px"] > 200),
        "faint_tiles": sum(1 for t in tiles if t["blue_pct"] < 0.05),
        "flagged_tiles": sum(1 for t in tiles if t["detection_flags"]),
        "months_present": len(tiles),
        "months_expected_in_years": len(years_present) * 12,
        "documented_pct": round(100 * sum(1 for t in tiles if t["meta"]) / len(tiles), 1),
    }

    return {
        "stats": stats,
        "tiles": tiles,
        "year_summary": year_summary,
        "station_epochs": [
            {"label": "Ulm", "start": "1835-01", "end": "1845-06",
             "note": "Earlier gauge; station/datum relationship to Neu-Ulm unverified."},
            {"label": "Neu-Ulm", "start": "1845-07", "end": "1893-12",
             "note": "Later gauge; the 1845 transition is a dataset break."},
        ],
        "constraints": [
            "Image corpus, not a numeric time series.",
            "No units, gauge datum, or station coordinates in the tiles.",
            "120 of 240 tiles have no per-tile metadata.",
            "24 duplicate files in tiles 2 and tiles 3.",
            "39 years are missing between 1835 and 1893.",
            "Rights remain with the Bayerisches Hauptstaatsarchiv.",
        ],
    }


def build_thumbs_and_patterns(data: dict):
    if THUMBS.exists():
        shutil.rmtree(THUMBS)
    if PATTERNS.exists():
        shutil.rmtree(PATTERNS)
    THUMBS.mkdir(parents=True)
    PATTERNS.mkdir(parents=True)

    by_key = {}
    for tile in data["tiles"]:
        src = (DASH / urllib.parse.unquote(tile["file"])).resolve()
        im = ImageOps.exif_transpose(Image.open(src).convert("RGB"))
        thumb = im.resize((124, 500), Image.Resampling.LANCZOS)
        out = THUMBS / f"{tile['year']}_{tile['month']:02d}.jpg"
        thumb.save(out, quality=86, optimize=True)
        tile["thumb"] = f"thumbs/{out.name}"
        by_key[(tile["year"], tile["month"])] = out

    f_year = font(26, True)
    f_month = font(15, False)
    f_small = font(13, False)
    f_tiny = font(11, False)
    cream = (244, 239, 230)
    ink = (43, 38, 32)
    muted = (120, 108, 93)
    line = (214, 204, 188)

    years = data["stats"]["years_present"]
    for year in years:
        row = [by_key.get((year, m)) for m in range(1, 13)]
        left, top, cell_w, cell_h, gap = 78, 48, 124, 500, 4
        width = left + 12 * cell_w + 11 * gap + 24
        height = top + cell_h + 34
        canvas = Image.new("RGB", (width, height), cream)
        draw = ImageDraw.Draw(canvas)
        draw.text((16, 16), str(year), font=f_year, fill=ink)
        for i, path in enumerate(row):
            x = left + i * (cell_w + gap)
            draw.text((x + 4, 16), MONTHS[i], font=f_month, fill=muted)
            if path:
                canvas.paste(Image.open(path).convert("RGB"), (x, top))
            else:
                draw.rectangle([x, top, x + cell_w, top + cell_h], outline=line, width=1)
                draw.text((x + 28, top + cell_h // 2), "missing", font=f_small, fill=muted)
        draw.line([(0, height - 1), (width, height - 1)], fill=line, width=1)
        canvas.save(PATTERNS / f"year_{year}.jpg", quality=87, optimize=True)

    cols = 4
    strip_w = 900
    gap = 10
    margin = 22
    strips = []
    for year in years:
        strip = Image.open(PATTERNS / f"year_{year}.jpg").convert("RGB")
        strip = strip.resize((strip_w, round(strip.height * strip_w / strip.width)), Image.Resampling.LANCZOS)
        strips.append(strip)
    strip_h = max(strip.height for strip in strips)
    rows = math.ceil(len(strips) / cols)
    width = margin * 2 + cols * strip_w + (cols - 1) * gap
    height = margin * 2 + rows * strip_h + (rows - 1) * gap
    canvas = Image.new("RGB", (width, height), cream)
    for index, strip in enumerate(strips):
        col = index % cols
        row = index // cols
        x = margin + col * (strip_w + gap)
        y = margin + row * (strip_h + gap)
        canvas.paste(strip, (x, y))
        ImageDraw.Draw(canvas).rectangle([x, y, x + strip_w - 1, y + strip.height - 1], outline=line, width=1)
    canvas.save(PATTERNS / "overview.jpg", quality=85, optimize=True)

    order = [by_key[(t["year"], t["month"])] for t in data["tiles"]]
    sw, sh, gap = 40, 161, 4
    left, top = 18, 34
    width = left + len(order) * (sw + gap) + 20
    height = top + sh + 50
    canvas = Image.new("RGB", (width, height), cream)
    draw = ImageDraw.Draw(canvas)
    prev_year = None
    for i, path in enumerate(order):
        year = int(path.name[:4])
        x = left + i * (sw + gap)
        if prev_year is not None and year != prev_year:
            draw.line([(x - gap // 2, 0), (x - gap // 2, height)], fill=(180, 166, 146), width=2)
            draw.text((x + 2, 10), str(year), font=f_tiny, fill=ink)
        elif prev_year is None:
            draw.text((x, 10), str(year), font=f_tiny, fill=ink)
        elif path.name[5:7] == "01":
            draw.text((x + 1, 10), str(year), font=f_tiny, fill=muted)
        canvas.paste(Image.open(path).resize((sw, sh), Image.Resampling.LANCZOS), (x, top))
        prev_year = year
    draw.text((left, height - 22), "1835", font=f_tiny, fill=muted)
    draw.text((width - 70, height - 22), "1893", font=f_tiny, fill=muted)
    canvas.save(PATTERNS / "long_run.jpg", quality=84, optimize=True)


def write_outputs(data: dict):
    (DASH / "manifest.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    (DASH / "data.js").write_text(
        "window.ICE_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    )
    columns = [
        "id", "year", "month", "month_name", "station", "station_source", "form",
        "source_scan", "source_status", "metadata", "duplicate", "doc_score",
        "doc_gaps", "tech_flags", "blue_pct", "red_px", "dark_pct", "grid_x",
        "grid_y", "width", "height", "bytes", "file",
    ]
    with (DASH / "manifest.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for t in data["tiles"]:
            writer.writerow({
                **{c: t.get(c) for c in columns if c not in {"metadata", "doc_gaps", "tech_flags"}},
                "metadata": "yes" if t["meta"] else "no",
                "doc_gaps": "; ".join(t["doc_gaps"]),
                "tech_flags": "; ".join(t["tech_flags"]),
            })


def main():
    data = build_manifest()
    build_thumbs_and_patterns(data)
    write_outputs(data)
    print(json.dumps(data["stats"], indent=1))


if __name__ == "__main__":
    main()
