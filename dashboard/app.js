(function () {
  "use strict";

  const DATA = window.ICE_DATA;
  if (!DATA || !Array.isArray(DATA.tiles)) {
    document.body.innerHTML = '<main><section class="panel"><h1>Dataset not loaded</h1><p>Run <code>python3 dashboard/build_dashboard.py</code> to generate <code>data.js</code>.</p></section></main>';
    return;
  }

  const TILES = DATA.tiles.slice();
  const STATS = DATA.stats;
  const YEARS = Array.from(new Set(TILES.map(function (t) { return t.year; }))).sort(function (a, b) { return a - b; });
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const REVIEW_KEY = "ice-reviews-v1";
  const VIEWS = ["overview", "patterns", "query", "validity", "about"];
  const FLAG_ANY = "any";

  let reviews = loadReviews();
  let currentResults = TILES.slice();
  let modalContext = [];
  let modalIndex = -1;
  let modalRotation = 0;
  let currentYear = YEARS[0];
  let toastTimer = null;

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  function pct(part, whole) {
    if (!whole) return 0;
    return Math.round((part / whole) * 1000) / 10;
  }

  function formatBytes(bytes) {
    if (!bytes && bytes !== 0) return "—";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(2) + " MB";
  }

  function monthName(tile) { return tile.month_name || MONTHS[tile.month - 1] || ""; }

  function monthLong(tile) { return MONTHS_LONG[tile.month - 1] || monthName(tile); }

  function displayYear(tile) { return tile.year + " " + monthName(tile); }

  function metadataLinked(tile) { return tile.source_status === "linked"; }

  function hasDetection(tile) { return Array.isArray(tile.detection_flags) && tile.detection_flags.length > 0; }

  function hasTech(tile) { return Array.isArray(tile.tech_flags) && tile.tech_flags.length > 0; }

  function hasSubstantialRed(tile) { return Number(tile.red_px) > 200; }

  function isFaint(tile) { return Number(tile.blue_pct) < 0.05 || (tile.tech_flags || []).indexOf("Faint blue ink") !== -1; }

  function allFlags(tile) {
    return Array.from(new Set([].concat(tile.tech_flags || [], tile.detection_flags || [])));
  }

  function reviewOf(tile) { return reviews[tile.id] || null; }

  function reviewStatusOf(tile) { return (reviewOf(tile) && reviewOf(tile).status) || "unreviewed"; }

  function reviewLabel(status) {
    return { unreviewed: "Unreviewed", "looks-good": "Looks good", "needs-review": "Needs review", reject: "Reject" }[status] || "Unreviewed";
  }

  function reviewTagClass(status) {
    return { "looks-good": "tag-good", "needs-review": "tag-warn", reject: "tag-bad" }[status] || "tag-neutral";
  }

  function loadReviews() {
    try {
      const raw = window.localStorage.getItem(REVIEW_KEY);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function persistReviews() {
    try {
      window.localStorage.setItem(REVIEW_KEY, JSON.stringify(reviews));
      return true;
    } catch (error) {
      showToast("Reviews kept for this session only — browser storage is unavailable.");
      return false;
    }
  }

  function showToast(message) {
    const toast = $("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { toast.hidden = true; }, 2600);
  }

  function downloadText(filename, text, type) {
    const blob = new Blob([text], { type: type || "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(function () { URL.revokeObjectURL(url); }, 800);
  }

  function setHash(name, replace) {
    try {
      const url = new URL(window.location.href);
      url.hash = name;
      if (replace) window.history.replaceState(null, "", url.toString());
      else window.history.pushState(null, "", url.toString());
    } catch (error) {
      if (replace) window.location.hash = name;
    }
  }

  function activateView(name, updateUrl) {
    const target = VIEWS.indexOf(name) === -1 ? "overview" : name;
    Array.prototype.forEach.call(document.querySelectorAll(".view"), function (view) {
      view.classList.toggle("is-active", view.getAttribute("data-view") === target);
    });
    Array.prototype.forEach.call(document.querySelectorAll(".navlink"), function (link) {
      link.classList.toggle("is-active", link.getAttribute("data-nav") === target);
    });
    if (updateUrl !== false) setHash(target, true);
    window.scrollTo({ top: 0, behavior: "instant" in document.documentElement.style ? "instant" : "auto" });
  }

  function bindNavigation() {
    document.addEventListener("click", function (event) {
      const trigger = event.target.closest("[data-nav]");
      if (!trigger) return;
      event.preventDefault();
      activateView(trigger.getAttribute("data-nav"), true);
    });
    window.addEventListener("hashchange", function () {
      const name = window.location.hash.replace(/^#/, "");
      if (VIEWS.indexOf(name) !== -1) activateView(name, false);
    });
  }

  function renderStats() {
    const items = [
      { value: STATS.unique_tiles, suffix: "", label: "Unique monthly tiles", note: STATS.files_on_disk + " files on disk · " + STATS.duplicate_files + " duplicates" },
      { value: STATS.years, suffix: "", label: "Years present", note: STATS.missing_year_count + " years absent inside 1835–1893" },
      { value: STATS.documented_pct, suffix: "%", label: "Metadata linked", note: STATS.linked_tiles + " of " + STATS.unique_tiles + " tiles carry per-tile metadata" },
      { value: STATS.missing_year_count, suffix: "", label: "Missing years", note: "No continuous annual series" },
      { value: STATS.flagged_tiles, suffix: "", label: "Detection flags", note: "Crop drift, pasted sheet, repaired base" },
      { value: STATS.red_tiles, suffix: "", label: "Substantial red ink", note: "August 1835 only · meaning unexplained" },
      { value: STATS.faint_tiles, suffix: "", label: "Faint blue ink", note: "Blue pixel share below 0.05%" },
      { value: STATS.avg_doc_score, suffix: "/100", label: "Average completeness", note: "Documentation coverage, not accuracy" }
    ];
    $("stats-grid").innerHTML = items.map(function (item) {
      return '<article class="stat"><div class="stat-value">' + esc(item.value) + '<span>' + esc(item.suffix) + '</span></div><div class="stat-label">' + esc(item.label) + '</div><div class="stat-note">' + esc(item.note) + '</div></article>';
    }).join("");

    const linked = TILES.filter(metadataLinked).length;
    const explicit = TILES.filter(function (t) { return t.station_source === "metadata"; }).length;
    const classified = TILES.filter(function (t) { return t.form !== "unclassified"; }).length;
    const techClean = TILES.filter(function (t) { return !hasTech(t) && !hasDetection(t); }).length;
    const reviewed = Object.keys(reviews).length;
    const bars = [
      { label: "Metadata linked", value: pct(linked, TILES.length), tone: "" },
      { label: "Source scan linked", value: pct(linked, TILES.length), tone: "" },
      { label: "Station explicit", value: pct(explicit, TILES.length), tone: "" },
      { label: "Form classified", value: pct(classified, TILES.length), tone: "is-warn" },
      { label: "No technical flag", value: pct(techClean, TILES.length), tone: "is-warn" },
      { label: "Human reviewed", value: pct(reviewed, TILES.length), tone: "is-warn" }
    ];
    $("documentation-bars").innerHTML = bars.map(barMarkup).join("");
    $("avg-score-note").textContent = STATS.avg_doc_score + " / 100 across " + STATS.unique_tiles + " tiles. The score measures how much catalogue information a tile carries, not whether its curve is correct.";
  }

  function barMarkup(bar) {
    const value = Math.max(0, Math.min(100, Number(bar.value) || 0));
    return '<div class="bar-row"><span class="bar-label">' + esc(bar.label) + '</span><span class="bar-track"><span class="bar-fill ' + esc(bar.tone || "") + '" style="width:' + value + '%"></span></span><span class="bar-value">' + value + '%</span></div>';
  }

  function renderCoverage() {
    const matrix = $("coverage-matrix");
    let html = '<div class="coverage-grid"><div class="cov-head"></div>';
    MONTHS.forEach(function (month) { html += '<div class="cov-head">' + month + '</div>'; });
    YEARS.forEach(function (year) {
      html += '<div class="cov-year">' + year + '</div>';
      for (let month = 1; month <= 12; month += 1) {
        const tile = TILES.find(function (t) { return t.year === year && t.month === month; });
        if (!tile) {
          html += '<div class="cov-cell is-missing" title="' + year + ' · ' + MONTHS[month - 1] + ' — missing"></div>';
          continue;
        }
        const classes = ["cov-cell"];
        classes.push(metadataLinked(tile) ? "is-documented" : "is-image");
        if (hasDetection(tile)) classes.push("is-flagged");
        const description = tile.id + " · " + tile.station + " · " + (metadataLinked(tile) ? "metadata linked" : "image only") + " · score " + tile.doc_score;
        html += '<div class="' + classes.join(" ") + '" title="' + esc(description) + '"><button type="button" data-tile="' + esc(tile.id) + '" aria-label="Open ' + esc(displayYear(tile)) + '"></button></div>';
      }
    });
    html += "</div>";
    matrix.innerHTML = html;

    const missing = STATS.missing_years || [];
    if (missing.length) {
      matrix.querySelector(".coverage-grid").insertAdjacentHTML("beforeend", '<div class="cov-year">gap</div><div class="cov-gap">' + missing.length + " years absent between 1835 and 1893 · listed below</div>");
    }
    $("missing-strip").innerHTML = "<strong>Missing years</strong>" + missing.map(function (year) { return "<span>" + year + "</span>"; }).join("");

    matrix.addEventListener("click", function (event) {
      const trigger = event.target.closest("[data-tile]");
      if (trigger) openModal(trigger.getAttribute("data-tile"), TILES.slice());
    });
  }

  function renderStations() {
    const epochs = DATA.station_epochs || [];
    $("station-rail").innerHTML = epochs.map(function (epoch) {
      const count = TILES.filter(function (t) { return t.station === epoch.label; }).length;
      return '<div class="station-block"><div class="station-name">' + esc(epoch.label) + '</div><div class="station-range">' + esc(epoch.start) + " → " + esc(epoch.end) + " · " + count + ' tiles</div><div class="station-note">' + esc(epoch.note) + "</div></div>";
    }).join("");
  }

  function patternVisibleTiles() {
    const onlyFlags = $("pattern-flag-filter").checked;
    const onlyMeta = $("pattern-meta-filter").checked;
    return TILES.filter(function (tile) {
      if (onlyFlags && !hasDetection(tile)) return false;
      if (onlyMeta && !metadataLinked(tile)) return false;
      return true;
    });
  }

  function renderPatternMatrix() {
    const host = $("pattern-matrix");
    const visible = patternVisibleTiles();
    const visibleIds = new Set(visible.map(function (t) { return t.id; }));
    let html = '<div class="matrix-head"><div></div>';
    MONTHS.forEach(function (month) { html += "<div>" + month + "</div>"; });
    html += "</div>";
    YEARS.forEach(function (year) {
      html += '<div class="matrix-row"><div class="matrix-year">' + year + '</div>';
      for (let month = 1; month <= 12; month += 1) {
        const tile = TILES.find(function (t) { return t.year === year && t.month === month; });
        if (!tile) {
          html += '<div class="matrix-cell is-muted"></div>';
          continue;
        }
        const classes = ["matrix-cell"];
        classes.push(metadataLinked(tile) ? "is-documented" : "is-image");
        if (hasDetection(tile)) classes.push("is-flagged");
        if (!visibleIds.has(tile.id)) classes.push("is-muted");
        html += '<div class="' + classes.join(" ") + '"><button type="button" data-tile="' + esc(tile.id) + '" aria-label="Open ' + esc(displayYear(tile)) + '"><img loading="lazy" src="' + esc(tile.thumb) + '" alt=""></button></div>';
      }
      html += "</div>";
    });
    host.innerHTML = html;
  }

  function renderYearStrip(year) {
    currentYear = year;
    const tiles = TILES.filter(function (t) { return t.year === year; });
    $("year-select").value = String(year);
    $("year-strip").src = "patterns/year_" + year + ".jpg";
    $("year-strip").alt = "Annual strip for " + year;
    const stations = Array.from(new Set(tiles.map(function (t) { return t.station; })));
    const forms = Array.from(new Set(tiles.map(function (t) { return t.form; })));
    const avg = tiles.reduce(function (sum, t) { return sum + Number(t.doc_score || 0); }, 0) / (tiles.length || 1);
    const flagged = tiles.filter(hasDetection).length;
    $("year-strip-meta").innerHTML = [
      "<span><strong>Months</strong> " + tiles.length + " / 12</span>",
      "<span><strong>Station</strong> " + esc(stations.join(" → ")) + "</span>",
      "<span><strong>Form</strong> " + esc(forms.join(" / ")) + "</span>",
      "<span><strong>Completeness</strong> " + avg.toFixed(1) + " / 100</span>",
      "<span><strong>Flagged</strong> " + flagged + "</span>"
    ].join("");
  }

  function initPatterns() {
    $("year-select").innerHTML = YEARS.map(function (year) { return '<option value="' + year + '">' + year + "</option>"; }).join("");
    renderPatternMatrix();
    renderYearStrip(YEARS[0]);

    $("pattern-flag-filter").addEventListener("change", renderPatternMatrix);
    $("pattern-meta-filter").addEventListener("change", renderPatternMatrix);
    $("pattern-reset").addEventListener("click", function () {
      $("pattern-flag-filter").checked = false;
      $("pattern-meta-filter").checked = false;
      renderPatternMatrix();
    });
    $("pattern-matrix").addEventListener("click", function (event) {
      const trigger = event.target.closest("[data-tile]");
      if (!trigger) return;
      const context = patternVisibleTiles();
      openModal(trigger.getAttribute("data-tile"), context.length ? context : TILES.slice());
    });
    $("year-select").addEventListener("change", function (event) { renderYearStrip(Number(event.target.value)); });
    $("year-prev").addEventListener("click", function () {
      const index = YEARS.indexOf(currentYear);
      renderYearStrip(YEARS[(index - 1 + YEARS.length) % YEARS.length]);
    });
    $("year-next").addEventListener("click", function () {
      const index = YEARS.indexOf(currentYear);
      renderYearStrip(YEARS[(index + 1) % YEARS.length]);
    });
  }

  function populateQueryControls() {
    const yearOptions = YEARS.map(function (year) { return '<option value="' + year + '">' + year + "</option>"; }).join("");
    $("f-year-from").innerHTML = yearOptions;
    $("f-year-to").innerHTML = yearOptions;
    $("f-year-from").value = String(YEARS[0]);
    $("f-year-to").value = String(YEARS[YEARS.length - 1]);

    $("f-month").innerHTML = '<option value="">Any month</option>' + MONTHS.map(function (month, index) {
      return '<option value="' + (index + 1) + '">' + month + "</option>";
    }).join("");

    const stations = Array.from(new Set(TILES.map(function (t) { return t.station; })));
    $("f-station").innerHTML = '<option value="">Any station</option>' + stations.map(function (station) {
      return '<option value="' + esc(station) + '">' + esc(station) + "</option>";
    }).join("");
  }

  function currentFilters() {
    return {
      yearFrom: Number($("f-year-from").value),
      yearTo: Number($("f-year-to").value),
      month: $("f-month").value,
      station: $("f-station").value,
      metadata: $("f-metadata").value,
      flag: $("f-flag").value,
      review: $("f-review").value,
      search: $("f-search").value.trim(),
      score: Number($("f-score").value),
      sort: $("f-sort").value
    };
  }

  function matchesFlag(tile, flag) {
    if (!flag) return true;
    if (flag === FLAG_ANY) return hasTech(tile) || hasDetection(tile);
    if (flag === "duplicate") return Boolean(tile.duplicate);
    if (flag === "faint") return isFaint(tile);
    if (flag === "red") return hasSubstantialRed(tile);
    if (flag === "pasted") return tile.form === "pasted 1837 sheet";
    if (flag === "detection") return hasDetection(tile);
    if (flag === "dimensions") return !tile.dimensions_ok;
    return true;
  }

  function filterTiles(filters) {
    const needle = filters.search.toLowerCase();
    const filtered = TILES.filter(function (tile) {
      if (filters.yearFrom && tile.year < filters.yearFrom) return false;
      if (filters.yearTo && tile.year > filters.yearTo) return false;
      if (filters.month && tile.month !== Number(filters.month)) return false;
      if (filters.station && tile.station !== filters.station) return false;
      if (filters.metadata === "yes" && !metadataLinked(tile)) return false;
      if (filters.metadata === "no" && metadataLinked(tile)) return false;
      if (filters.review && reviewStatusOf(tile) !== filters.review) return false;
      if (!matchesFlag(tile, filters.flag)) return false;
      if (Number(tile.doc_score) < filters.score) return false;
      if (needle) {
        const haystack = [tile.id, tile.year, monthName(tile), monthLong(tile), tile.station, tile.form, tile.source_scan, allFlags(tile).join(" ")].join(" ").toLowerCase();
        if (haystack.indexOf(needle) === -1) return false;
      }
      return true;
    });

    filtered.sort(function (a, b) {
      switch (filters.sort) {
        case "year-desc": return b.year - a.year || b.month - a.month;
        case "score-asc": return a.doc_score - b.doc_score || a.year - b.year || a.month - b.month;
        case "score-desc": return b.doc_score - a.doc_score || a.year - b.year || a.month - b.month;
        case "blue-desc": return b.blue_pct - a.blue_pct || a.year - b.year;
        case "red-desc": return b.red_px - a.red_px || a.year - b.year;
        default: return a.year - b.year || a.month - b.month;
      }
    });
    return filtered;
  }

  function flagSummary(tile) {
    const flags = allFlags(tile);
    if (!flags.length) return '<span class="microcopy">—</span>';
    const shown = flags.slice(0, 2).map(function (flag) {
      return '<span class="tag ' + (hasDetection(tile) ? "tag-bad" : "tag-warn") + '">' + esc(flag) + "</span>";
    });
    if (flags.length > 2) shown.push('<span class="tag tag-neutral">+' + (flags.length - 2) + "</span>");
    return shown.join("");
  }

  function scoreCell(tile) {
    const score = Number(tile.doc_score) || 0;
    return '<span class="score-mini"><span class="score-mini-track"><span style="width:' + Math.max(0, Math.min(100, score)) + '%;background:' + (score >= 70 ? "var(--green)" : score >= 40 ? "var(--amber)" : "var(--oxblood)") + '"></span></span><span class="num">' + score + "</span></span>";
  }

  function renderQuery(filters) {
    const body = $("query-body");
    body.innerHTML = currentResults.map(function (tile) {
      const status = reviewStatusOf(tile);
      return "<tr>" +
        '<td class="num">' + tile.year + "</td>" +
        "<td>" + esc(monthName(tile)) + "</td>" +
        '<td>' + esc(tile.station) + '<div class="microcopy">' + esc(tile.station_source) + "</div></td>" +
        '<td>' + esc(tile.form) + "</td>" +
        "<td>" + (metadataLinked(tile) ? '<span class="tag tag-good">Linked</span>' : '<span class="tag tag-warn">Image only</span>') + "</td>" +
        '<td class="num">' + esc(tile.source_scan || "—") + "</td>" +
        "<td>" + scoreCell(tile) + "</td>" +
        "<td>" + flagSummary(tile) + "</td>" +
        '<td><span class="tag ' + reviewTagClass(status) + '">' + esc(reviewLabel(status)) + "</span></td>" +
        '<td><button class="link-button" type="button" data-open="' + esc(tile.id) + '">Open</button></td>' +
        "</tr>";
    }).join("");

    $("query-body").parentElement.parentElement.style.display = currentResults.length ? "" : "none";
    $("query-empty").hidden = currentResults.length > 0;
    $("query-count").textContent = currentResults.length + " record" + (currentResults.length === 1 ? "" : "s");
    renderResultSummary(filters);
  }

  function renderResultSummary(filters) {
    const count = currentResults.length;
    const years = Array.from(new Set(currentResults.map(function (t) { return t.year; })));
    const linked = currentResults.filter(metadataLinked).length;
    const flagged = currentResults.filter(function (t) { return hasTech(t) || hasDetection(t); }).length;
    const avg = count ? (currentResults.reduce(function (sum, t) { return sum + Number(t.doc_score || 0); }, 0) / count).toFixed(1) : "—";
    const range = years.length === 1 ? String(years[0]) : years.length ? years[0] + "–" + years[years.length - 1] : "none";
    const host = $("result-summary");

    if (!count) {
      host.innerHTML = "<span><strong>0</strong> months selected</span>";
      return;
    }

    host.innerHTML = [
      "<span><strong>" + count + "</strong> of " + TILES.length + " months</span>",
      "<span><strong>" + years.length + "</strong> " + (years.length === 1 ? "year" : "years") + " · " + range + "</span>",
      "<span><strong>" + linked + "</strong> metadata-linked</span>",
      "<span><strong>" + flagged + "</strong> flagged</span>",
      "<span><strong>" + avg + "</strong> avg completeness</span>"
    ].join("");

    const audit = document.createElement("button");
    audit.type = "button";
    audit.className = "link-button";
    audit.textContent = "Audit this selection";
    audit.addEventListener("click", function () { renderValidityCheck(filters); });
    host.appendChild(audit);
  }

  function renderValidityCheck(filters) {
    const host = $("validity-check-content");
    const count = currentResults.length;
    const panel = $("validity-check-panel");
    panel.hidden = false;

    if (!count) {
      host.innerHTML = '<p class="microcopy">No records selected. Adjust the query first.</p>';
      panel.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }

    const years = Array.from(new Set(currentResults.map(function (t) { return t.year; }))).sort();
    const stations = Array.from(new Set(currentResults.map(function (t) { return t.station; })));
    const linked = currentResults.filter(metadataLinked).length;
    const explicit = currentResults.filter(function (t) { return t.station_source === "metadata"; }).length;
    const flagged = currentResults.filter(function (t) { return hasTech(t) || hasDetection(t); }).length;
    const red = currentResults.filter(hasSubstantialRed).length;
    const faint = currentResults.filter(isFaint).length;
    const lowScore = currentResults.filter(function (t) { return Number(t.doc_score) < 60; }).length;
    const avg = (currentResults.reduce(function (sum, t) { return sum + Number(t.doc_score || 0); }, 0) / count).toFixed(1);

    const supports = [];
    const caveats = [];
    supports.push("Visual inspection and month-to-month comparison within the selection.");
    supports.push("Catalogue-level provenance checks for the selected tiles.");
    if (linked === count) supports.push("Metadata-backed browsing: every selected tile is linked to a source scan.");
    else caveats.push((count - linked) + " selected tiles are image-only and have no per-tile metadata.");
    if (stations.length > 1) caveats.push("The selection crosses the Ulm / Neu-Ulm station boundary; do not compare levels across it without a datum study.");
    if (red) caveats.push(red + " selected tile(s) contain substantial red ink. Its meaning is undocumented; do not call it ice.");
    if (faint) caveats.push(faint + " selected tile(s) are faint-ink risks (blue pixel share below 0.05%).");
    if (flagged) caveats.push(flagged + " selected tile(s) carry technical or detection flags.");
    if (lowScore) caveats.push(lowScore + " selected tile(s) score below 60/100 for completeness.");
    caveats.push("None of the selected tiles carries units, a gauge datum, or extracted values, so no centimetre claim is supported.");

    const yearPhrase = years.length === 1 ? "1 year (" + years[0] + ")" : years.length + " years (" + years[0] + "–" + years[years.length - 1] + ")";
    host.innerHTML =
      '<p class="lede">' + count + " months · " + yearPhrase + " · " + esc(stations.join(" / ")) + " · average completeness " + avg + " / 100.</p>" +
      '<div class="split"><div><h3>What the selection supports</h3><ul class="issue-list">' + supports.map(function (item) { return "<li>" + esc(item) + "</li>"; }).join("") + "</ul></div>" +
      '<div><h3>What remains unsafe</h3><ul class="issue-list">' + caveats.map(function (item) { return '<li class="is-warn">' + esc(item) + "</li>"; }).join("") + "</ul></div></div>" +
      '<p class="microcopy">Selection context: ' + esc(JSON.stringify(filters)) + "</p>";
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function runQuery(options) {
    const opts = options || {};
    const filters = currentFilters();
    if (filters.yearFrom > filters.yearTo) {
      const swap = $("f-year-from").value;
      $("f-year-from").value = $("f-year-to").value;
      $("f-year-to").value = swap;
      filters.yearFrom = Number($("f-year-from").value);
      filters.yearTo = Number($("f-year-to").value);
      showToast("Year range swapped.");
    }
    currentResults = filterTiles(filters);
    renderQuery(filters);
    const checkPanel = $("validity-check-panel");
    if (checkPanel && !checkPanel.hidden) checkPanel.hidden = true;
    if (opts.sync !== false) syncQueryUrl(filters);
    return filters;
  }

  function buildQueryParams(filters) {
    const params = new URLSearchParams();
    if (filters.yearFrom !== YEARS[0]) params.set("year_from", String(filters.yearFrom));
    if (filters.yearTo !== YEARS[YEARS.length - 1]) params.set("year_to", String(filters.yearTo));
    if (filters.month) params.set("month", filters.month);
    if (filters.station) params.set("station", filters.station);
    if (filters.metadata) params.set("metadata", filters.metadata);
    if (filters.flag) params.set("flag", filters.flag);
    if (filters.review) params.set("review", filters.review);
    if (filters.search) params.set("q", filters.search);
    if (filters.score) params.set("score", String(filters.score));
    if (filters.sort !== "year-asc") params.set("sort", filters.sort);
    return params;
  }

  function syncQueryUrl(filters) {
    try {
      const url = new URL(window.location.href);
      const params = buildQueryParams(filters);
      url.search = params.toString();
      url.hash = "query";
      window.history.replaceState(null, "", url.toString());
    } catch (error) {
      return;
    }
  }

  function hydrateQueryFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const hasAny = ["year_from", "year_to", "month", "station", "metadata", "flag", "review", "q", "score", "sort"].some(function (key) { return params.has(key); });
    if (!hasAny) return false;

    const from = Number(params.get("year_from"));
    const to = Number(params.get("year_to"));
    if (YEARS.indexOf(from) !== -1) $("f-year-from").value = String(from);
    if (YEARS.indexOf(to) !== -1) $("f-year-to").value = String(to);
    const month = params.get("month");
    if (month && Number(month) >= 1 && Number(month) <= 12) $("f-month").value = month;
    const station = params.get("station");
    if (station && Array.prototype.some.call($("f-station").options, function (option) { return option.value === station; })) $("f-station").value = station;
    const metadata = params.get("metadata");
    if (["yes", "no"].indexOf(metadata) !== -1) $("f-metadata").value = metadata;
    const flag = params.get("flag");
    if (flag && Array.prototype.some.call($("f-flag").options, function (option) { return option.value === flag; })) $("f-flag").value = flag;
    const review = params.get("review");
    if (review && Array.prototype.some.call($("f-review").options, function (option) { return option.value === review; })) $("f-review").value = review;
    const search = params.get("q");
    if (search) $("f-search").value = search;
    const score = Number(params.get("score"));
    if (!Number.isNaN(score) && score >= 0 && score <= 100) {
      $("f-score").value = String(score);
    }
    const sort = params.get("sort");
    if (sort && Array.prototype.some.call($("f-sort").options, function (option) { return option.value === sort; })) $("f-sort").value = sort;
    $("f-score-value").textContent = $("f-score").value;
    return true;
  }

  function resetQuery() {
    $("f-year-from").value = String(YEARS[0]);
    $("f-year-to").value = String(YEARS[YEARS.length - 1]);
    $("f-month").value = "";
    $("f-station").value = "";
    $("f-metadata").value = "";
    $("f-flag").value = "";
    $("f-review").value = "";
    $("f-search").value = "";
    $("f-score").value = "0";
    $("f-score-value").textContent = "0";
    $("f-sort").value = "year-asc";
    $("validity-check-panel").hidden = true;
    runQuery({ sync: true });
  }

  function initQuery() {
    populateQueryControls();
    hydrateQueryFromUrl();
    runQuery({ sync: false });

    $("f-score").addEventListener("input", function (event) { $("f-score-value").textContent = event.target.value; });
    $("f-search").addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        runQuery({ sync: true });
      }
    });
    $("apply-query").addEventListener("click", function () { runQuery({ sync: true }); });
    $("reset-query").addEventListener("click", resetQuery);
    $("copy-query").addEventListener("click", copyQueryLink);
    $("export-csv").addEventListener("click", exportCsv);
    $("export-json").addEventListener("click", exportJson);
    $("close-check").addEventListener("click", function () { $("validity-check-panel").hidden = true; });
    $("query-body").addEventListener("click", function (event) {
      const trigger = event.target.closest("[data-open]");
      if (trigger) openModal(trigger.getAttribute("data-open"), currentResults);
    });
  }

  function copyQueryLink() {
    const filters = currentFilters();
    const url = new URL(window.location.href);
    url.search = buildQueryParams(filters).toString();
    url.hash = "query";
    const text = url.toString();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { showToast("Query link copied."); }).catch(function () { fallbackCopy(text); });
    } else {
      fallbackCopy(text);
    }
  }

  function fallbackCopy(text) {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "readonly");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
      showToast("Query link copied.");
    } catch (error) {
      showToast("Copy failed. The query is visible in the address bar.");
    }
    document.body.removeChild(area);
  }

  function exportCsv() {
    const columns = ["id", "year", "month", "month_name", "station", "station_source", "form", "source_scan", "source_status", "doc_score", "needs_review", "duplicate", "width", "height", "bytes", "blue_pct", "red_px", "grid_x", "grid_y", "detection_flags", "tech_flags", "doc_gaps", "review_status", "review_updated", "review_note", "file"];
    const rows = currentResults.map(function (tile) {
      const review = reviewOf(tile);
      return columns.map(function (column) {
        if (column === "review_status") return reviewStatusOf(tile);
        if (column === "review_updated") return (review && review.updated) || "";
        if (column === "review_note") return (review && review.note) || "";
        if (["detection_flags", "tech_flags", "doc_gaps"].indexOf(column) !== -1) return (tile[column] || []).join("; ");
        return tile[column] == null ? "" : tile[column];
      });
    });
    const csv = [columns.join(",")].concat(rows.map(function (row) { return row.map(csvEscape).join(","); })).join("\r\n");
    downloadText("ice-level-query.csv", csv, "text/csv;charset=utf-8");
    showToast(currentResults.length + " records exported as CSV.");
  }

  function csvEscape(value) {
    const text = String(value);
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  function exportJson() {
    const payload = {
      exported_at: new Date().toISOString(),
      dataset: "ICE LEVEL DATASET",
      count: currentResults.length,
      filters: currentFilters(),
      records: currentResults.map(function (tile) {
        return Object.assign({}, tile, { review: reviewOf(tile) });
      })
    };
    downloadText("ice-level-query.json", JSON.stringify(payload, null, 2), "application/json");
    showToast(currentResults.length + " records exported as JSON.");
  }

  function initValidity() {
    const useCases = [
      ["Browse and compare chart forms", "yes", "The images are faithful derivatives of archival scans; visual comparison is supported."],
      ["Study historical chart conventions", "yes", "Form eras and paper changes are visible and partly classified."],
      ["Build a chart-understanding benchmark", "conditional", "Requires a hand-traced gold set and per-era calibration; known traps remain."],
      ["Automated curve extraction", "conditional", "Possible after calibration; faint ink and the 1837 pasted sheet will produce errors."],
      ["Within-year seasonal shape", "conditional", "Legible for well-inked months, but no units or datum and some curves are faint."],
      ["Absolute water level in centimetres", "no", "No units, gauge datum, station coordinates, or extracted values."],
      ["Interannual trend estimation", "no", "39 missing years, an unverified 1845 station break, and no datum."],
      ["Flood frequency or climate reconstruction", "no", "The corpus is not a validated, gap-free measurement series."],
      ["Cross-station comparison", "no", "Ulm and Neu-Ulm are separate epochs with no established datum relationship."],
      ["Redistribute the images", "no", "No licence is included; rights remain with the Bayerisches Hauptstaatsarchiv."]
    ];
    const labels = { yes: "Supported", conditional: "Conditional", no: "Not supported" };
    $("use-table").innerHTML = useCases.map(function (item) {
      return '<div class="use-row"><span class="use-name">' + esc(item[0]) + '</span><span class="use-verdict ' + item[1] + '">' + labels[item[1]] + '</span><span class="use-reason">' + esc(item[2]) + "</span></div>";
    }).join("");

    renderValidityBars();
    renderIssues();
    renderReviewProgress();
    renderRiskGrid();
    renderValidityStatement();

    $("download-report").addEventListener("click", downloadValidityReport);
    $("export-reviews").addEventListener("click", exportReviews);
    $("export-reviews-top").addEventListener("click", exportReviews);
    $("clear-reviews").addEventListener("click", clearReviews);
    $("open-risky-query").addEventListener("click", openRiskyQuery);
    $("risk-grid").addEventListener("click", function (event) {
      const trigger = event.target.closest("[data-risk]");
      if (!trigger) return;
      const context = topRiskTiles();
      openModal(trigger.getAttribute("data-risk"), context);
    });
  }

  function renderValidityBars() {
    const linked = TILES.filter(metadataLinked).length;
    const explicit = TILES.filter(function (t) { return t.station_source === "metadata"; }).length;
    const classified = TILES.filter(function (t) { return t.form !== "unclassified"; }).length;
    const techClean = TILES.filter(function (t) { return !hasTech(t) && !hasDetection(t); }).length;
    const notFaint = TILES.filter(function (t) { return !isFaint(t); }).length;
    const reviewed = Object.keys(reviews).length;
    $("validity-bars").innerHTML = [
      { label: "Metadata linked", value: pct(linked, TILES.length), tone: "" },
      { label: "Station explicit", value: pct(explicit, TILES.length), tone: "" },
      { label: "Form classified", value: pct(classified, TILES.length), tone: "is-warn" },
      { label: "No technical flag", value: pct(techClean, TILES.length), tone: "is-warn" },
      { label: "No faint-ink risk", value: pct(notFaint, TILES.length), tone: "is-warn" },
      { label: "Human reviewed", value: pct(reviewed, TILES.length), tone: "is-warn" }
    ].map(barMarkup).join("");
  }

  function renderIssues() {
    const issues = [
      ["39 years absent", "No annual continuity between 1835 and 1893; gaps are structural, not random."],
      ["1845 station break", "Ulm becomes Neu-Ulm in July 1845. The gauge-zero relationship is unverified."],
      ["120 image-only tiles", "1864–1893 carry no per-tile metadata; station and form are inferred or unclassified."],
      ["18 detection flags", "Crop drift, a pasted 1837 sheet, and repaired bases in 1845 and 1848."],
      ["50 faint-ink tiles", "Blue pixel share below 0.05%. The curve may be partially invisible."],
      ["One red-ink outlier", "August 1835 contains 4,232 red pixels. The meaning is undocumented."],
      ["No units or datum", "Tiles show shape, not centimetres. Absolute levels are unsupported."],
      ["Rights unresolved", "No licence is present; redistribution requires archive permission."]
    ];
    $("issue-list").innerHTML = issues.map(function (issue, index) {
      return '<li class="' + (index > 3 ? "is-warn" : "") + '"><div><strong>' + esc(issue[0]) + ".</strong> " + esc(issue[1]) + "</div></li>";
    }).join("");
  }

  function renderReviewProgress() {
    const statuses = ["looks-good", "needs-review", "reject"];
    const counts = { "looks-good": 0, "needs-review": 0, reject: 0 };
    Object.keys(reviews).forEach(function (id) {
      const status = reviews[id] && reviews[id].status;
      if (counts[status] != null) counts[status] += 1;
    });
    const reviewed = Object.keys(reviews).length;
    const withNotes = Object.keys(reviews).filter(function (id) { return reviews[id] && reviews[id].note; }).length;
    $("review-progress").innerHTML =
      '<div class="progress-total"><div><p class="eyebrow">Reviewed</p><strong>' + reviewed + "</strong> of " + TILES.length + "</div><span>" + pct(reviewed, TILES.length) + "%</span></div>" +
      '<div class="progress-legend">' +
      statuses.map(function (status) { return "<span>" + reviewLabel(status) + " <b>" + counts[status] + "</b></span>"; }).join("") +
      "<span>With notes <b>" + withNotes + "</b></span>" +
      "<span>Remaining <b>" + (TILES.length - reviewed) + "</b></span>" +
      "</div>";
    renderValidityBars();
  }

  function riskScore(tile) {
    let score = 0;
    score += (tile.detection_flags || []).length * 12;
    score += (tile.tech_flags || []).length * 5;
    if (tile.form === "pasted 1837 sheet") score += 14;
    if (tile.station_source === "inferred") score += 6;
    if (isFaint(tile)) score += 6;
    if (hasSubstantialRed(tile)) score += 40;
    if ((tile.detection_flags || []).join(" ").toLowerCase().indexOf("repaired") !== -1) score += 10;
    if (!tile.source_scan) score += 5;
    score += Math.max(0, 80 - Number(tile.doc_score || 0)) * 0.45;
    return Math.round(score);
  }

  function riskSignature(tile) {
    const detection = (tile.detection_flags || []).join(" ").toLowerCase();
    const primary = detection.indexOf("pasted") !== -1 ? "pasted" : detection.indexOf("repaired") !== -1 ? "repair" : detection.indexOf("top") !== -1 ? "top-drift" : detection.indexOf("base") !== -1 ? "base-drift" : "";
    return [tile.form, tile.station_source, (tile.tech_flags || []).slice().sort().join("|"), primary, hasSubstantialRed(tile) ? "red" : "", tile.source_scan ? "linked" : "image-only"].join("::");
  }

  function topRiskTiles() {
    const sorted = TILES.slice().sort(function (a, b) {
      return riskScore(b) - riskScore(a) || Number(a.doc_score) - Number(b.doc_score);
    });
    const seen = new Set();
    const seenYears = new Set();
    const picked = [];
    sorted.forEach(function (tile) {
      const signature = riskSignature(tile);
      if (seen.has(signature) || seenYears.has(tile.year)) return;
      seen.add(signature);
      seenYears.add(tile.year);
      picked.push(tile);
    });
    return picked.slice(0, 6);
  }

  function renderRiskGrid() {
    const risks = topRiskTiles();
    $("risk-grid").innerHTML = risks.map(function (tile) {
      const reasons = [];
      if (tile.form === "pasted 1837 sheet") reasons.push("Pasted sheet");
      if ((tile.detection_flags || []).length) reasons.push("Detection flag");
      if (isFaint(tile)) reasons.push("Faint ink");
      if (!tile.source_scan) reasons.push("Image only");
      if (hasSubstantialRed(tile)) reasons.push("Red ink");
      return '<button type="button" class="risk-card" data-risk="' + esc(tile.id) + '">' +
        '<span class="eyebrow">' + esc(displayYear(tile)) + " · risk " + riskScore(tile) + "</span>" +
        "<strong>" + esc(tile.station) + " · " + esc(monthLong(tile)) + "</strong>" +
        "<span>" + esc(tile.station_source) + " station · completeness " + tile.doc_score + "/100</span>" +
        '<span class="tag tag-warn">' + esc(reasons.slice(0, 3).join(" · ") || "Low metadata") + "</span>" +
        "</button>";
    }).join("");
  }

  function renderValidityStatement() {
    $("validity-statement").textContent =
      "This corpus is valid as a visual archive of 240 monthly gauge charts from Ulm and Neu-Ulm, and conditionally valid as a chart-understanding benchmark once a hand-traced gold set exists. " +
      "It is not valid for absolute water levels, interannual trends, flood frequency, or climate reconstruction: it carries no units, gauge datum, station coordinates, or extracted values; 39 years are missing; and the July 1845 station change has no verified datum continuity. " +
      "The red ink in August 1835 is a documented visual outlier, not evidence of ice. Any scientific use must state these limits and avoid centimetre claims.";
  }

  function reviewsPayload() {
    return {
      exported_at: new Date().toISOString(),
      dataset: "ICE LEVEL DATASET",
      key: REVIEW_KEY,
      count: Object.keys(reviews).length,
      reviews: reviews
    };
  }

  function exportReviews() {
    downloadText("ice-level-reviews.json", JSON.stringify(reviewsPayload(), null, 2), "application/json");
    showToast(Object.keys(reviews).length + " reviews exported.");
  }

  function clearReviews() {
    if (!window.confirm("Clear all local reviews? This cannot be undone. Export first if you need them.")) return;
    reviews = {};
    try { window.localStorage.removeItem(REVIEW_KEY); } catch (error) { showToast("Reviews cleared for this session only."); }
    renderReviewProgress();
    renderRiskGrid();
    const currentTile = modalContext[modalIndex];
    if (!document.getElementById("detail-modal").hidden && currentTile) {
      modalRotation = 0;
      fillModal(currentTile);
    }
    showToast("Local reviews cleared.");
  }

  function openRiskyQuery() {
    activateView("query", true);
    $("f-year-from").value = String(YEARS[0]);
    $("f-year-to").value = String(YEARS[YEARS.length - 1]);
    $("f-month").value = "";
    $("f-station").value = "";
    $("f-metadata").value = "";
    $("f-flag").value = "";
    $("f-review").value = "unreviewed";
    $("f-search").value = "";
    $("f-score").value = "0";
    $("f-score-value").textContent = "0";
    $("f-sort").value = "score-asc";
    runQuery({ sync: true });
    showToast("Showing all unreviewed tiles, lowest completeness first.");
  }

  function downloadValidityReport() {
    const lines = [
      "# ICE LEVEL DATASET — validity report",
      "",
      "Generated: " + new Date().toISOString(),
      "Corpus: 240 monthly gauge-chart tiles, 20 years, 1835–1893, Ulm / Neu-Ulm.",
      "",
      "## Verdict",
      "",
      "Supported: browsing, visual comparison, and review workflows.",
      "Conditional: chart-understanding benchmark and curve extraction, after a hand-traced gold set and per-era calibration.",
      "Not supported: absolute water levels, interannual trends, flood frequency, climate reconstruction, cross-station comparison.",
      "",
      "## Why",
      "",
      "- No units, gauge datum, station coordinates, or extracted values.",
      "- 120 of 240 tiles have no per-tile metadata; 1864–1893 forms are unclassified.",
      "- 39 years are absent inside the 1835–1893 envelope.",
      "- Ulm becomes Neu-Ulm in July 1845; datum continuity is unverified.",
      "- 18 detection flags, including a pasted 1837 sheet and repaired bases.",
      "- 50 tiles are faint-ink risks; substantial red ink appears only in August 1835.",
      "- No licence is included; rights remain with the Bayerisches Hauptstaatsarchiv.",
      "",
      "## Integrity checks",
      "",
      "- Files on disk: " + STATS.files_on_disk + "; unique tiles: " + STATS.unique_tiles + "; duplicate files: " + STATS.duplicate_files + ".",
      "- Average documentation completeness: " + STATS.avg_doc_score + "/100 (documentation, not accuracy).",
      "- Human reviews stored locally: " + Object.keys(reviews).length + " of " + TILES.length + ".",
      "",
      "## Required caveat",
      "",
      "A tile is a picture of a chart, not a measurement. The station changes in 1845 and 39 years are missing; continuity is an assumption, not a fact. The red series in August 1835 is unexplained and must not be labelled ice without archival evidence."
    ];
    downloadText("ice-validity-report.md", lines.join("\n"), "text/markdown;charset=utf-8");
    showToast("Validity report downloaded.");
  }

  function metaRow(label, value) {
    return "<dt>" + esc(label) + "</dt><dd>" + value + "</dd>";
  }

  function checklistMarkup(tile) {
    const checks = [
      ["Per-tile metadata", metadataLinked(tile) ? "good" : "bad", metadataLinked(tile) ? "linked" : "missing"],
      ["Source scan linked", tile.source_scan ? "good" : "bad", tile.source_scan ? "linked" : "missing"],
      ["Station explicit", tile.station_source === "metadata" ? "good" : "warn", tile.station_source],
      ["Form classified", tile.form === "unclassified" ? "bad" : "good", tile.form === "unclassified" ? "unclassified" : "classified"],
      ["Dimensions nominal", tile.dimensions_ok ? "good" : "bad", tile.width + " × " + tile.height],
      ["Technical flags", hasDetection(tile) ? "bad" : hasTech(tile) ? "warn" : "good", hasDetection(tile) ? "detection flag" : hasTech(tile) ? "technical flag" : "clean"]
    ];
    return checks.map(function (check) {
      return '<div class="check-row is-' + check[1] + '"><i></i><span>' + esc(check[0]) + " · " + esc(check[2]) + "</span></div>";
    }).join("");
  }

  function flagList(label, flags) {
    if (!flags || !flags.length) return "";
    return '<div class="flag-block"><h3>' + esc(label) + '</h3><div class="flag-list">' + flags.map(function (flag) { return '<span class="tag tag-warn">' + esc(flag) + "</span>"; }).join("") + "</div></div>";
  }

  function openModal(id, context) {
    const tile = TILES.find(function (item) { return item.id === id; });
    if (!tile) return;
    const list = (context && context.length ? context : TILES).slice();
    const existing = list.findIndex(function (item) { return item.id === id; });
    if (existing === -1) list.unshift(tile);
    modalContext = list;
    modalIndex = list.findIndex(function (item) { return item.id === id; });
    modalRotation = 0;
    fillModal(tile);
    $("detail-modal").hidden = false;
    document.body.classList.add("modal-open");
    window.setTimeout(function () { $("modal-close").focus(); }, 30);
  }

  function fillModal(tile) {
    const status = reviewStatusOf(tile);
    $("modal-image").src = tile.thumb || tile.file;
    $("modal-image").alt = "Chart for " + monthLong(tile) + " " + tile.year;
    $("modal-image").style.transform = "";
    $("modal-image-caption").textContent = tile.id + " · " + tile.width + " × " + tile.height + " · " + formatBytes(tile.bytes);
    $("modal-original").href = tile.file;
    $("modal-kicker").textContent = tile.id + " · " + tile.station + " · " + (metadataLinked(tile) ? "metadata linked" : "image only");
    $("modal-title").textContent = monthLong(tile) + " " + tile.year;

    const badges = ['<span class="tag tag-neutral">' + esc(tile.station) + " · " + esc(tile.station_source) + "</span>"];
    badges.push(metadataLinked(tile) ? '<span class="tag tag-good">Metadata linked</span>' : '<span class="tag tag-warn">Image only</span>');
    if (hasSubstantialRed(tile)) badges.push('<span class="tag tag-bad">Red ink</span>');
    if (isFaint(tile)) badges.push('<span class="tag tag-warn">Faint ink</span>');
    if (hasDetection(tile)) badges.push('<span class="tag tag-bad">' + tile.detection_flags.length + " detection flag" + (tile.detection_flags.length === 1 ? "" : "s") + "</span>");
    badges.push('<span class="tag ' + reviewTagClass(status) + '">' + esc(reviewLabel(status)) + "</span>");
    $("modal-badges").innerHTML = badges.join("");

    $("modal-score").textContent = tile.doc_score + " / 100";
    $("modal-score-bar").style.width = Math.max(0, Math.min(100, tile.doc_score)) + "%";
    $("modal-score-bar").style.background = tile.doc_score >= 70 ? "var(--green)" : tile.doc_score >= 40 ? "var(--amber)" : "var(--oxblood)";
    $("modal-checklist").innerHTML = checklistMarkup(tile);

    $("modal-meta").innerHTML = [
      metaRow("Record", esc(tile.id)),
      metaRow("File", '<code title="' + esc(tile.file) + '">' + esc(tile.file) + "</code>"),
      metaRow("Dimensions", tile.width + " × " + tile.height + " px"),
      metaRow("File size", formatBytes(tile.bytes)),
      metaRow("SHA-256", '<code title="' + esc(tile.sha256) + '">' + esc(String(tile.sha256).slice(0, 18)) + "…</code>"),
      metaRow("Ruling", tile.grid_x + " × " + tile.grid_y + " px"),
      metaRow("Mean luma", tile.mean_luma),
      metaRow("Blue ink", tile.blue_pct + "% of pixels"),
      metaRow("Red ink", tile.red_px + " px"),
      metaRow("Source scan", esc(tile.source_scan || "not linked")),
      metaRow("Form", esc(tile.form)),
      metaRow("Station basis", esc(tile.station_source)),
      metaRow("Duplicate", tile.duplicate ? "yes" : "no")
    ].join("");

    const flagHost = $("modal-flags");
    let flagsHtml = flagList("Technical flags", tile.tech_flags);
    flagsHtml += flagList("Detection flags", tile.detection_flags);
    flagsHtml += flagList("Documentation gaps", tile.doc_gaps);
    flagHost.innerHTML = flagsHtml || '<p class="microcopy">No technical or documentation flags on this tile.</p>';

    fillReviewForm(tile);
    $("modal-prev").disabled = modalIndex <= 0;
    $("modal-next").disabled = modalIndex >= modalContext.length - 1;
  }

  function fillReviewForm(tile) {
    if (!tile) return;
    const review = reviewOf(tile) || {};
    $("review-status").value = review.status || "unreviewed";
    $("rv-curve").checked = Boolean(review.curve);
    $("rv-gap").checked = Boolean(review.gap);
    $("rv-faded").checked = Boolean(review.faded);
    $("rv-red").checked = Boolean(review.red);
    $("rv-crop").checked = Boolean(review.crop);
    $("rv-station").checked = Boolean(review.station);
    $("rv-note").value = review.note || "";
    $("review-saved-note").textContent = review.updated ? "Last saved " + new Date(review.updated).toLocaleString() : "Not reviewed yet.";
    $("modal-review-state").textContent = reviewLabel(review.status || "unreviewed");
  }

  function saveReview() {
    const tile = modalContext[modalIndex];
    if (!tile) return;
    const record = {
      status: $("review-status").value,
      curve: $("rv-curve").checked,
      gap: $("rv-gap").checked,
      faded: $("rv-faded").checked,
      red: $("rv-red").checked,
      crop: $("rv-crop").checked,
      station: $("rv-station").checked,
      note: $("rv-note").value.trim(),
      updated: new Date().toISOString()
    };
    const hasDetail = record.curve || record.gap || record.faded || record.red || record.crop || record.station || record.note;
    if (record.status === "unreviewed" && !hasDetail) delete reviews[tile.id];
    else reviews[tile.id] = record;

    persistReviews();
    $("review-saved-note").textContent = "Saved locally " + new Date(record.updated).toLocaleTimeString();
    $("modal-review-state").textContent = reviewLabel(record.status);
    const badgeRow = $("modal-badges");
    const oldBadge = badgeRow.querySelector(".tag:last-child");
    if (oldBadge) {
      oldBadge.className = "tag " + reviewTagClass(record.status);
      oldBadge.textContent = reviewLabel(record.status);
    }
    renderReviewProgress();
    renderRiskGrid();
    if (currentResults.length && $("view-query").classList.contains("is-active")) {
      renderQuery(currentFilters());
    }
    showToast("Review saved for " + tile.id + ".");
  }

  function closeModal() {
    $("detail-modal").hidden = true;
    document.body.classList.remove("modal-open");
    $("modal-image").style.transform = "";
  }

  function modalStep(delta) {
    const next = modalIndex + delta;
    if (next < 0 || next >= modalContext.length) return;
    modalIndex = next;
    modalRotation = 0;
    fillModal(modalContext[modalIndex]);
    $("detail-modal").querySelector(".modal-dialog").scrollTop = 0;
  }

  function initModal() {
    $("modal-close").addEventListener("click", closeModal);
    $("detail-modal").addEventListener("click", function (event) {
      if (event.target.getAttribute("data-close-modal") === "true") closeModal();
    });
    $("modal-rotate").addEventListener("click", function () {
      modalRotation = (modalRotation + 90) % 360;
      $("modal-image").style.transform = modalRotation ? "rotate(" + modalRotation + "deg)" : "";
    });
    $("modal-prev").addEventListener("click", function () { modalStep(-1); });
    $("modal-next").addEventListener("click", function () { modalStep(1); });
    $("save-review").addEventListener("click", saveReview);
    document.addEventListener("keydown", function (event) {
      if ($("detail-modal").hidden) return;
      if (event.key === "Escape") closeModal();
      if (["INPUT", "TEXTAREA", "SELECT"].indexOf(event.target.tagName) !== -1) return;
      if (event.key === "ArrowLeft") modalStep(-1);
      if (event.key === "ArrowRight") modalStep(1);
    });
  }

  function init() {
    bindNavigation();
    renderStats();
    renderCoverage();
    renderStations();
    initPatterns();
    initQuery();
    initValidity();
    initModal();

    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(window.location.search);
    const hasQueryParams = ["year_from", "year_to", "month", "station", "metadata", "flag", "review", "q", "score", "sort"].some(function (key) { return params.has(key); });
    const initial = hasQueryParams ? "query" : VIEWS.indexOf(hash) !== -1 ? hash : "overview";
    activateView(initial, false);
  }

  init();
}());
