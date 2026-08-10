/* ==========================================================================
   TarXiv redesign mockups — shared data + widget builders
   ========================================================================== */

/* ------------------------------------------------------------ theme utils */

const THEME_KEY = "tarxiv-mock-theme";

function currentTheme() {
  return document.documentElement.dataset.theme || "light";
}

const themeListeners = [];
function onThemeChange(fn) { themeListeners.push(fn); }

function toggleTheme() {
  const next = currentTheme() === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* ignore */ }
  themeListeners.forEach((fn) => fn(next));
}

/* Chart chrome per theme (mirrors shared.css tokens — Plotly can't read CSS vars) */
const CHART_CHROME = {
  light: {
    surface: "#ffffff", ink: "#15191b", ink2: "#5a6166", ink3: "#8b9196",
    grid: "#ececef", axis: "#c9ccd0",
  },
  dark: {
    surface: "#1c2224", ink: "#f2f4f5", ink2: "#a9b2b7", ink3: "#737d82",
    grid: "#262e31", axis: "#3d4649",
  },
};

/* Filter colours — validated with the dataviz palette validator (all-pairs,
   scatter) against #ffffff (light) and #1c2224 (dark). Marker symbols are the
   secondary encoding for the warn-band CVD pairs; the photometry table is the
   relief channel for the light-mode amber. */
const FILTER_STYLE = {
  "ZTF g":   { light: "#199e70", dark: "#199e70", symbol: "circle" },
  "ZTF r":   { light: "#e34948", dark: "#e34948", symbol: "square" },
  "ATLAS c": { light: "#2a78d6", dark: "#3987e5", symbol: "diamond" },
  "ATLAS o": { light: "#eda100", dark: "#c98500", symbol: "triangle-up" },
};

/* ------------------------------------------------------------ sample data */

/* SN 2023ixf in M101 — real object, plausible fabricated photometry. */
const OBJ = {
  id: "SN 2023ixf",
  tarxiv_id: "TXV-2023-051901",
  ra_deg: 210.910674,
  dec_deg: 54.31165,
  ra_hms: "14:03:38.56",
  dec_dms: "+54:18:41.9",
  type: "SN II",
  redshift: 0.000804,
  host: "M101 (NGC 5457)",
  discovery_date: "2023-05-19 17:27:15",
  discovery_mjd: 60083.727,
  reporting_group: "Itagaki",
  discovery_source: "Itagaki (ALeRCE)",
  peak_mag: "10.9 (o)",
  update_date: "2023-09-14 03:12:44",
};

function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* Type II-P-ish model: fast rise, slow plateau, drop-off. */
function modelMag(mjd, offset) {
  const t = mjd - OBJ.discovery_mjd;
  const peak = 11.05 + offset;
  if (t < 0) return NaN;
  if (t < 6) return peak + 3.4 * Math.pow(1 - t / 6, 1.7); // rise
  if (t < 85) return peak + 0.011 * (t - 6);               // plateau
  return peak + 0.011 * 79 + 0.055 * (t - 85);             // decline
}

function genPhotometry() {
  const rng = mulberry32(20230519);
  const series = [];
  const cfg = [
    { name: "ZTF g",   survey: "ZTF",   offset: 0.55, cadence: 2.4, start: 0.9 },
    { name: "ZTF r",   survey: "ZTF",   offset: 0.18, cadence: 2.4, start: 1.1 },
    { name: "ATLAS c", survey: "ATLAS", offset: 0.34, cadence: 3.1, start: 0.4 },
    { name: "ATLAS o", survey: "ATLAS", offset: 0.0,  cadence: 3.1, start: 0.2 },
  ];
  for (const c of cfg) {
    const det = { x: [], y: [], err: [] };
    let t = c.start;
    while (t < 128) {
      if (rng() > 0.18) { // weather losses
        const mjd = OBJ.discovery_mjd + t + (rng() - 0.5) * 0.6;
        const m = modelMag(mjd, c.offset);
        if (!Number.isNaN(m)) {
          const err = 0.015 + 0.012 * Math.max(0, m - 11) + rng() * 0.02;
          det.x.push(+mjd.toFixed(3));
          det.y.push(+(m + (rng() - 0.5) * 2 * err * 1.4).toFixed(3));
          det.err.push(+err.toFixed(3));
        }
      }
      t += c.cadence * (0.75 + rng() * 0.5);
    }
    /* pre-discovery non-detection limits */
    const lim = { x: [], y: [] };
    let tl = -14 + rng() * 2;
    while (tl < -0.6) {
      lim.x.push(+(OBJ.discovery_mjd + tl).toFixed(3));
      lim.y.push(+(19.1 + rng() * 0.8 - c.offset * 0.3).toFixed(2));
      tl += c.cadence * (0.8 + rng() * 0.5);
    }
    series.push({ ...c, det, lim });
  }
  return series;
}

const PHOTOMETRY = genPhotometry();

/* ---------------------------------------------------------- metadata dump */

const SOURCES = [
  {
    key: "tns", label: "TNS",
    fields: {
      "Identifier": "2023ixf",
      "Object Type": "SN II",
      "Discovery Date": "2023-05-19 17:27:15",
      "Reporting Group": "Itagaki",
      "Discovery Data Source": "ALeRCE",
      "Redshift": "0.000804",
      "Host Name": "M101 (NGC 5457)",
      "Magnitude": "14.90",
      "Magnitude Filter": "Clear",
      "RA (deg)": "210.910674",
      "Dec (deg)": "54.311650",
    },
  },
  {
    key: "ztf", label: "ZTF",
    fields: {
      "Identifier": "ZTF23aaklqou",
      "RA (deg)": "210.910671",
      "Dec (deg)": "54.311646",
      "Detections": "141",
      "First Detection (MJD)": "60084.16",
      "Latest Detection (MJD)": "60211.42",
    },
    lists: {
      "Peak Magnitude": [
        { Filter: "g", Date: "60090.21", Magnitude: "11.58", "Mag Rate": "−0.42" },
        { Filter: "r", Date: "60090.24", Magnitude: "11.21", "Mag Rate": "−0.38" },
      ],
      "Latest Detection": [
        { Filter: "g", Date: "60211.38", Magnitude: "14.62", "Mag Rate": "+0.05" },
        { Filter: "r", Date: "60211.42", Magnitude: "13.94", "Mag Rate": "+0.05" },
      ],
    },
  },
  {
    key: "atlas", label: "ATLAS",
    fields: {
      "Identifier": "ATLAS23mtp",
      "RA (deg)": "210.910668",
      "Dec (deg)": "54.311654",
      "Detections": "96",
      "First Detection (MJD)": "60083.94",
      "Latest Detection (MJD)": "60209.87",
    },
    lists: {
      "Peak Magnitude": [
        { Filter: "c", Date: "60089.97", Magnitude: "11.39", "Mag Rate": "−0.35" },
        { Filter: "o", Date: "60090.01", Magnitude: "10.94", "Mag Rate": "−0.33" },
      ],
      "Latest Non-detection": [
        { Filter: "o", Date: "60082.91", Magnitude: "> 19.24", "Mag Rate": "—" },
      ],
    },
  },
  {
    key: "sherlock", label: "Sherlock",
    fields: {
      "Association Type": "SN",
      "Catalogue Object ID": "NGC 5457",
      "Catalogue Object Type": "galaxy",
      "Catalogue Table": "NED-D/GLADE",
      "Classification Reliability": "1",
      "Best Distance": "6.85 Mpc",
      "Best Distance Flag": "z-independent",
      "Best Distance Source": "NED-D (TRGB)",
      "Separation (arcsec)": "263.7",
      "North Separation (arcsec)": "−134.2",
      "East Separation (arcsec)": "+226.9",
      "Physical Separation (kpc)": "8.76",
    },
  },
];

const TAGS = [
  { name: "followup", color: "#b31b1b", owner: "personal" },
  { name: "SN II", color: "#2a78d6", owner: "team · FTX" },
  { name: "bright", color: "#c98500", owner: "team · FTX" },
];

const CITATIONS_BIB = `@article{2019PASP..131a8002B,
  author = {{Bellm}, Eric C. and {Kulkarni}, Shrinivas R. and et al.},
  title = "{The Zwicky Transient Facility: System Overview}",
  journal = {PASP}, year = 2019, volume = {131}, pages = {018002},
  doi = {10.1088/1538-3873/aaecbe}
}
@article{2018PASP..130f4505T,
  author = {{Tonry}, J.~L. and {Denneau}, L. and et al.},
  title = "{ATLAS: A High-cadence All-sky Survey System}",
  journal = {PASP}, year = 2018, volume = {130}, pages = {064505},
  doi = {10.1088/1538-3873/aabadf}
}
@article{2020PASP..132h5002S,
  author = {{Smith}, K.~W. and {Williams}, R.~D. and et al.},
  title = "{Design and Operation of the ATLAS Transient Science Server}",
  journal = {PASP}, year = 2020, volume = {132}, pages = {085002},
  doi = {10.1088/1538-3873/ab936e}
}`;

function fullJsonDump() {
  const doc = {
    tarxiv_id: OBJ.tarxiv_id, source: "tns", source_id: "2023ixf",
    ra_deg: OBJ.ra_deg, dec_deg: OBJ.dec_deg,
    ra_hms: OBJ.ra_hms, dec_dms: OBJ.dec_dms,
    discovery_date: OBJ.discovery_date, update_date: OBJ.update_date,
    data_sources: Object.fromEntries(
      SOURCES.map((s) => [s.key, { ...s.fields, ...(s.lists || {}) }])
    ),
  };
  return JSON.stringify(doc, null, 2);
}

/* -------------------------------------------------------------- lightcurve */

function lightcurveTraces(theme) {
  const traces = [];
  for (const s of PHOTOMETRY) {
    const st = FILTER_STYLE[s.name];
    const color = st[theme];
    traces.push({
      x: s.det.x, y: s.det.y,
      error_y: { type: "data", array: s.det.err, visible: true, width: 0, thickness: 1.2, color },
      mode: "markers", type: "scatter",
      name: s.name,
      legendgroup: s.survey, legendgrouptitle: { text: s.survey },
      marker: { color, size: 8, symbol: st.symbol,
                line: { width: 1, color: CHART_CHROME[theme].surface } },
      hovertemplate: `<b>${s.name}</b>  MJD %{x:.2f}<br>%{y:.2f} ± %{customdata:.2f} mag` +
        `<extra></extra>`,
      customdata: s.det.err,
    });
    if (s.lim.x.length) {
      traces.push({
        x: s.lim.x, y: s.lim.y,
        mode: "markers", type: "scatter",
        name: `${s.name} limit`,
        legendgroup: s.survey, showlegend: false,
        marker: { color, size: 9, symbol: "triangle-down-open", opacity: 0.55 },
        hovertemplate: `<b>${s.name}</b> non-detection  MJD %{x:.2f}<br>limit %{y:.2f} mag<extra></extra>`,
      });
    }
  }
  return traces;
}

function lightcurveLayout(theme, opts = {}) {
  const c = CHART_CHROME[theme];
  const compact = !!opts.compact;
  return {
    paper_bgcolor: c.surface,
    plot_bgcolor: c.surface,
    font: { family: "Inter, system-ui, sans-serif", size: 12, color: c.ink2 },
    margin: { l: 52, r: 12, t: compact ? 8 : 12, b: 42 },
    xaxis: {
      title: { text: "MJD", font: { size: 11, color: c.ink3 }, standoff: 8 },
      tickformat: "d",
      gridcolor: c.grid, zeroline: false, linecolor: c.axis,
      ticks: "outside", tickcolor: c.axis, ticklen: 4,
      tickfont: { size: 11, color: c.ink3 },
    },
    yaxis: {
      title: { text: "Apparent magnitude", font: { size: 11, color: c.ink3 }, standoff: 6 },
      autorange: "reversed",
      gridcolor: c.grid, zeroline: false, linecolor: c.axis,
      ticks: "outside", tickcolor: c.axis, ticklen: 4,
      tickfont: { size: 11, color: c.ink3 },
    },
    legend: {
      orientation: "h", x: 0, y: 1.02, xanchor: "left", yanchor: "bottom",
      font: { size: 11.5, color: c.ink2 },
      grouptitlefont: { size: 11, color: c.ink3 },
      itemsizing: "constant",
    },
    hoverlabel: {
      bgcolor: theme === "light" ? "#15191b" : "#f2f4f5",
      font: { color: theme === "light" ? "#f2f4f5" : "#15191b", size: 12,
              family: "Inter, system-ui, sans-serif" },
      bordercolor: "transparent",
    },
    dragmode: "zoom",
    showlegend: true,
  };
}

function mountLightcurve(el, opts = {}) {
  if (typeof Plotly === "undefined") {
    el.innerHTML = `<div class="aladin-fallback" style="position:static;height:100%">
      Plotly failed to load (offline?) — lightcurve preview unavailable.</div>`;
    return;
  }
  const cfg = { responsive: true, displaylogo: false,
                modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"] };
  const draw = (theme) =>
    Plotly.react(el, lightcurveTraces(theme), lightcurveLayout(theme, opts), cfg);
  draw(currentTheme());
  onThemeChange(draw);
}

/* photometry table — the relief channel for sub-3:1 marks + accessibility */
function photometryTableHTML() {
  const theme = currentTheme();
  const rows = [];
  for (const s of PHOTOMETRY) {
    const color = FILTER_STYLE[s.name][theme];
    s.det.x.forEach((x, i) => rows.push({
      mjd: x, filter: s.name, color,
      mag: s.det.y[i].toFixed(2), err: s.det.err[i].toFixed(2), kind: "detection",
    }));
    s.lim.x.forEach((x, i) => rows.push({
      mjd: x, filter: s.name, color,
      mag: "> " + s.lim.y[i].toFixed(2), err: "—", kind: "limit",
    }));
  }
  rows.sort((a, b) => a.mjd - b.mjd);
  return `<table class="data-table">
    <thead><tr><th>MJD</th><th>Filter</th><th>Mag</th><th>σ</th><th>Type</th></tr></thead>
    <tbody>${rows.map((r) => `<tr>
      <td class="mono">${r.mjd.toFixed(2)}</td>
      <td><span class="swatch" style="background:${r.color}"></span>${r.filter}</td>
      <td class="mono">${r.mag}</td><td class="mono">${r.err}</td>
      <td class="faint">${r.kind}</td></tr>`).join("")}
    </tbody></table>`;
}

/* ---------------------------------------------------------------- aladin */

function mountAladin(el) {
  const fallback = () => {
    el.innerHTML = `<div class="aladin-fallback">
      <strong>Aladin Lite unavailable</strong>
      <span>CDN script did not load — sky view shows here<br>
      (PanSTARRS DR1 colour, centred on ${OBJ.id})</span></div>`;
  };
  if (typeof A === "undefined") { fallback(); return; }
  A.init.then(() => {
    const aladin = A.aladin(el, {
      survey: "P/PanSTARRS/DR1/color-z-zg-g",
      target: `${OBJ.ra_deg} ${OBJ.dec_deg}`,
      fov: 0.14,
      showFullscreenControl: true,
      showLayersControl: false,
      showFrame: false,
      showCooGridControl: false,
      reticleColor: "#e34948",
      reticleSize: 26,
    });
    const cat = A.catalog({ shape: "circle", color: "#e34948", sourceSize: 16 });
    aladin.addCatalog(cat);
    cat.addSources([A.source(OBJ.ra_deg, OBJ.dec_deg, { name: OBJ.id })]);
  }).catch(fallback);
}

/* -------------------------------------------------- metadata tab builders */

function metaListTable(title, rows) {
  const cols = Object.keys(rows[0]);
  return `<div style="margin-top:12px">
    <div class="faint small" style="font-weight:600;letter-spacing:.05em;text-transform:uppercase;font-size:10.5px;margin-bottom:4px">${title}</div>
    <table class="data-table">
      <thead><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((r) =>
        `<tr>${cols.map((c) => `<td>${r[c]}</td>`).join("")}</tr>`).join("")}
      </tbody></table></div>`;
}

function metaFieldsHTML(src) {
  const rows = Object.entries(src.fields).map(([k, v]) =>
    `<tr><td class="k">${k}</td><td class="v">${v}</td></tr>`).join("");
  const lists = src.lists
    ? Object.entries(src.lists).map(([t, rws]) => metaListTable(t, rws)).join("")
    : "";
  return `<table class="meta-rows"><tbody>${rows}</tbody></table>${lists}`;
}

/* Renders tab buttons + panel into `container`. mode: "pill" | "underline" */
function mountMetaTabs(container, mode = "pill") {
  const nav = document.createElement("div");
  nav.className = "tabs" + (mode === "underline" ? " underline" : "");
  const panel = document.createElement("div");
  panel.style.cssText = "margin-top:10px;min-height:0;overflow:auto;flex:1";
  const select = (key) => {
    nav.querySelectorAll("button").forEach((b) =>
      b.classList.toggle("active", b.dataset.key === key));
    panel.innerHTML = metaFieldsHTML(SOURCES.find((s) => s.key === key));
  };
  for (const s of SOURCES) {
    const b = document.createElement("button");
    b.textContent = s.label;
    b.dataset.key = s.key;
    b.onclick = () => select(s.key);
    nav.appendChild(b);
  }
  container.appendChild(nav);
  container.appendChild(panel);
  select("tns");
}

/* ------------------------------------------------------------------ tags */

function tagsHTML() {
  return TAGS.map((t) => `<span class="chip" style="background:${t.color}18;border-color:${t.color}40">
      <span class="dot" style="background:${t.color}"></span>${t.name}
      <span class="k">${t.owner}</span>
      <button class="badge-x" title="Remove">×</button></span>`).join(" ");
}

function tagAssignHTML() {
  return `<div style="display:flex;gap:8px;margin-top:12px">
    <div class="search-box" style="min-width:0;flex:1">
      <input placeholder="Select tag…" list="tag-options">
      <datalist id="tag-options"><option value="followup"><option value="host-z"><option value="spectrum-needed"></datalist>
    </div>
    <button class="btn btn-outline">Assign</button></div>`;
}

/* -------------------------------------------------------------- misc UI  */

function copyText(text, btn) {
  navigator.clipboard?.writeText(text).then(() => {
    if (!btn) return;
    const old = btn.innerHTML;
    btn.innerHTML = "✓";
    setTimeout(() => { btn.innerHTML = old; }, 1200);
  });
}

const ICONS = {
  copy: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  search: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>`,
  sun: `<svg class="icon-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>`,
  moon: `<svg class="icon-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>`,
  chev: `<svg class="chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>`,
  curve: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 17c4-1 5-9 9-9s5 6 9 5"/></svg>`,
  globe: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></svg>`,
  table: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/></svg>`,
  tag: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 2H2v10l9.3 9.3a2 2 0 0 0 2.8 0l7.2-7.2a2 2 0 0 0 0-2.8z"/><circle cx="7" cy="7" r="1.5" fill="currentColor" stroke="none"/></svg>`,
  quote: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 8h10M7 12h6M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 4V6a2 2 0 0 1 1-2z"/></svg>`,
  json: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 4a3 3 0 0 0-3 3v2a3 3 0 0 1-2 3 3 3 0 0 1 2 3v2a3 3 0 0 0 3 3M16 4a3 3 0 0 1 3 3v2a3 3 0 0 0 2 3 3 3 0 0 0-2 3v2a3 3 0 0 1-3 3"/></svg>`,
};

/* Shared topbar. `active` = nav item key. `variant`: "full" | "slim" */
function topbarHTML(active = "lightcurve") {
  const links = [
    ["home", "Home"], ["lightcurve", "Lightcurve"], ["cone", "Cone Search"],
    ["alerts", "Alerts"], ["tagged", "Tagged"],
  ];
  return `
    <a class="wordmark" href="index.html">tar<span class="x">X</span>iv</a>
    <nav class="topnav">${links.map(([k, l]) =>
      `<a href="#" class="${k === active ? "active" : ""}">${l}</a>`).join("")}
    </nav>
    <div class="spacer"></div>
    <div class="search-box">${ICONS.search}<input placeholder="Search object ID…" value="2023ixf"><kbd>⏎</kbd></div>
    <button class="icon-btn" onclick="toggleTheme()" title="Toggle theme">${ICONS.sun}${ICONS.moon}</button>
    <div style="width:30px;height:30px;border-radius:50%;background:var(--primary-soft-2);color:var(--primary-ink);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px" title="Signed in as J. Leland">JL</div>`;
}

function coordsCopyHTML(id = "coords-copy") {
  const coords = `${OBJ.ra_hms} ${OBJ.dec_dms}`;
  return `<span class="copy-wrap">
    <span class="mono" style="font-weight:600">${coords}</span>
    <button class="icon-btn sm" id="${id}" title="Copy coordinates"
      onclick="copyText('${coords}', this)">${ICONS.copy}</button></span>`;
}
