"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import maplibregl from "maplibre-gl";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BarrioGap {
  barrio:     string;
  nombre:     string;  // original GeoJSON property (always present)
  comuna:     number;
  n:          number;
  alpha_med:  number;
  pct_alpha:  number;
  usd_m2_med: number;
  usd_m2_p25: number;
  usd_m2_p75: number;
  pct_precio: number;
  ratio_gap:  number | null;
  pct_ratio:  number;
  confiable:  boolean;
}

type SortKey = "ratio_gap" | "alpha_med" | "usd_m2_med" | "n";

const COMUNAS = Array.from({ length: 15 }, (_, i) => i + 1);

// ── Color scale ───────────────────────────────────────────────────────────────

const GAP_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  "case",
  ["==", ["get", "confiable"], false],
  "#334155",
  [
    "interpolate", ["linear"], ["get", "ratio_gap"],
    0.7, "#10b981",
    1.0, "#84cc16",
    1.3, "#eab308",
    1.7, "#f97316",
    2.2, "#ef4444",
    3.0, "#b91c1c",
  ],
];

// ── Popup builders ────────────────────────────────────────────────────────────

function buildBarrioPopup(p: BarrioGap): string {
  const badge = p.confiable
    ? `<span style="background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);color:#6ee7b7;padding:1px 6px;border-radius:4px;font-size:10px">Confiable (n=${p.n})</span>`
    : `<span style="background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.25);color:#fcd34d;padding:1px 6px;border-radius:4px;font-size:10px">Muestra chica (n=${p.n})</span>`;
  const rc = p.ratio_gap == null ? "#94a3b8" : p.ratio_gap < 1.0 ? "#10b981" : p.ratio_gap < 1.5 ? "#eab308" : "#ef4444";
  const ratioBlock = p.ratio_gap != null
    ? `<div style="background:rgba(255,255,255,0.06);border-radius:4px;padding:6px 8px;margin-top:6px;display:flex;align-items:center;justify-content:space-between">
         <div>
           <div style="color:#64748b;font-size:10px">Gap de Valor</div>
           <div style="font-size:18px;font-weight:700;color:${rc}">${p.ratio_gap.toFixed(3)}</div>
           <div style="color:#64748b;font-size:9px">precio / alpha score</div>
         </div>
         <div style="text-align:right">
           <div style="color:#64748b;font-size:10px">Percentil</div>
           <div style="font-weight:600;color:#e2e8f0">p${p.pct_ratio}</div>
         </div>
       </div>`
    : `<div style="background:rgba(255,255,255,0.04);border-radius:4px;padding:6px 8px;margin-top:6px;color:#64748b;font-size:11px">Sin datos suficientes</div>`;
  return `
    <div style="font-family:system-ui;font-size:12px;color:#e2e8f0;min-width:220px">
      <div style="margin-bottom:6px">
        <div style="font-weight:700;font-size:14px;margin-bottom:3px">${p.nombre || p.barrio}</div>
        <div style="color:#64748b;font-size:9px;margin-bottom:3px">Comuna ${p.comuna}</div>
        ${badge}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:8px">
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">Alpha Score</div>
          <div style="font-weight:600">${p.alpha_med != null ? p.alpha_med.toFixed(1) : "—"}</div>
          <div style="color:#64748b;font-size:9px">p${p.pct_alpha} CABA</div>
        </div>
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">USD/m²</div>
          <div style="font-weight:600">${p.usd_m2_med != null ? `$${Math.round(p.usd_m2_med).toLocaleString()}` : "—"}</div>
          <div style="color:#64748b;font-size:9px">p${p.pct_precio} CABA</div>
        </div>
      </div>
      ${ratioBlock}
    </div>`;
}

function buildStationPopup(name: string, linea: string): string {
  return `<div style="font-family:system-ui;font-size:12px;color:#e2e8f0;padding:2px 4px">
    <div style="font-weight:600">${name}</div>
    ${linea ? `<div style="color:#94a3b8;font-size:10px">Línea ${linea}</div>` : ""}
  </div>`;
}

// ── Casos destacados ──────────────────────────────────────────────────────────
// Excluye barrios en precio_norm exactamente 0 o 100 (artefacto min-max).

const CASOS = [
  {
    barrio: "San Nicolas", badge: "Mejor Valor", color: "#10b981", ratio: 0.722,
    text:   "Alpha p85 (accesibilidad top — muy cerca del subte, alta densidad de POIs), precio p8 ($2.115/m²) — el mercado no refleja los fundamentals. Centro histórico con alta conectividad pero baja demanda residencial premium.",
  },
  {
    barrio: "Belgrano", badge: "Equilibrado", color: "#eab308", ratio: 1.542,
    text:   "Alpha p92 (uno de los más accesibles), precio p58 — ratio 1.54 indica prima moderada y razonable. Buen punto de referencia: los fundamentals justifican gran parte del precio.",
  },
  {
    barrio: "Villa Del Parque", badge: "Mayor Prima", color: "#ef4444", ratio: 2.938,
    text:   "Alpha p8 (accesibilidad baja, lejos del subte, pocos POIs), precio p50 ($2.706/m²) — ratio 2.94, el más alto de CABA. La demanda paga precio de zona residencial tradicional que el modelo objetivo no justifica.",
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ValueGapMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map          = useRef<maplibregl.Map | null>(null);
  const popup        = useRef<maplibregl.Popup | null>(null);

  const [barrios, setBarrios]               = useState<BarrioGap[]>([]);
  const [allNombres, setAllNombres]         = useState<string[]>([]);
  const [loaded, setLoaded]                 = useState(false);
  const [sortKey, setSortKey]               = useState<SortKey>("ratio_gap");
  const [sortAsc, setSortAsc]               = useState(true);
  const [selectedBarrio, setSelectedBarrio] = useState<string | null>(null);
  const [activeTab, setActiveTab]           = useState<"tabla" | "casos" | "metodologia">("tabla");

  // Filters + layer toggles
  const [selectedComunas, setSelectedComunas] = useState<number[]>([]);
  const [barrioSearch, setBarrioSearch]       = useState("");
  const [showSubte, setShowSubte]             = useState(true);
  const [showLabels, setShowLabels]           = useState(false);

  // ── Load GeoJSON ──────────────────────────────────────────────────────────
  useEffect(() => {
    fetch("/value_gap_caba.geojson")
      .then((r) => r.json())
      .then((data) => {
        const all: BarrioGap[] = data.features.map(
          (f: { properties: BarrioGap }) => f.properties
        );
        setAllNombres(all.map((p) => p.nombre || p.barrio));
        setBarrios(all.filter((p) => p.confiable && p.ratio_gap != null));
      });
  }, []);

  // ── Map init ──────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style:     "https://tiles.openfreemap.org/styles/dark",
      center:    [-58.44, -34.62],
      zoom:      11.2,
      minZoom:   9,
      maxZoom:   16,
    });

    popup.current = new maplibregl.Popup({
      closeButton: false, closeOnClick: false,
      className: "rsi-popup", maxWidth: "280px",
    });

    map.current.on("load", () => {
      const m = map.current!;

      // ── Gap choropleth ──
      m.addSource("gap", { type: "geojson", data: "/value_gap_caba.geojson" });
      m.addLayer({ id: "gap-fill", type: "fill", source: "gap",
        paint: { "fill-color": GAP_COLOR_EXPR, "fill-opacity": 0.80 } });
      m.addLayer({ id: "gap-border", type: "line", source: "gap",
        paint: { "line-color": "#ffffff", "line-width": 0.5, "line-opacity": 0.18 } });

      // Dim overlay — active when filter set
      m.addLayer({ id: "gap-dim", type: "fill", source: "gap",
        paint: { "fill-color": "#0a0f1e", "fill-opacity": 0.72 },
        filter: ["==", 1, 0] });

      // ── Comunas borders ──
      m.addSource("comunas", { type: "geojson", data: "/comunas_caba.geojson" });
      m.addLayer({ id: "comunas-border", type: "line", source: "comunas",
        paint: { "line-color": "#94a3b8", "line-width": 1.5, "line-opacity": 0.35, "line-dasharray": [4, 3] } });
      // Highlight for selected comunas — filter updated dynamically
      m.addLayer({ id: "comunas-highlight", type: "line", source: "comunas",
        paint: { "line-color": "#ffffff", "line-width": 2.5, "line-opacity": 0.75 },
        filter: ["==", 1, 0] });

      // ── Subte lines ──
      m.addSource("subte-lines", { type: "geojson", data: "/subte_lines_caba.geojson" });
      m.addLayer({ id: "subte-lines-bg", type: "line", source: "subte-lines",
        paint: { "line-color": "#000000", "line-width": 4, "line-opacity": 0.5 } });
      m.addLayer({ id: "subte-lines-fg", type: "line", source: "subte-lines",
        paint: { "line-color": ["get", "colour"], "line-width": 2.5, "line-opacity": 0.95 } });

      // ── Subte stations ──
      m.addSource("subte-stations", { type: "geojson", data: "/subte_stations_caba.geojson" });
      m.addLayer({ id: "subte-stations", type: "circle", source: "subte-stations",
        paint: {
          "circle-radius": 4,
          "circle-color": ["get", "colour"],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.95,
        } });

      // ── Barrio labels ──
      m.addLayer({ id: "barrio-labels", type: "symbol", source: "gap",
        layout: {
          "text-field": ["get", "nombre"],
          "text-size": 9,
          "text-anchor": "center",
          "text-allow-overlap": false,
          "text-max-width": 8,
          "visibility": "none",
        },
        paint: {
          "text-color": "#e2e8f0",
          "text-opacity": 0.75,
          "text-halo-color": "#0a0f1e",
          "text-halo-width": 1.5,
        } });

      // ── Selection highlight ──
      m.addLayer({ id: "gap-highlight", type: "line", source: "gap",
        paint: { "line-color": "#ffffff", "line-width": 2.5, "line-opacity": 0.85 },
        filter: ["==", ["get", "nombre"], ""] });

      setLoaded(true);
    });

    // Barrio hover
    map.current.on("mousemove", "gap-fill", (e) => {
      if (!e.features?.length) return;
      map.current!.getCanvas().style.cursor = "pointer";
      const p = e.features[0].properties as BarrioGap;
      popup.current!.setLngLat(e.lngLat).setHTML(buildBarrioPopup(p)).addTo(map.current!);
    });
    map.current.on("mouseleave", "gap-fill", () => {
      map.current!.getCanvas().style.cursor = "";
      popup.current?.remove();
    });
    map.current.on("click", "gap-fill", (e) => {
      if (!e.features?.length) return;
      const p = e.features[0].properties as BarrioGap;
      const id = p.nombre || p.barrio;
      setSelectedBarrio(id);
      map.current!.setFilter("gap-highlight", ["==", ["get", "nombre"], id]);
    });

    // Station hover
    map.current.on("mousemove", "subte-stations", (e) => {
      if (!e.features?.length) return;
      map.current!.getCanvas().style.cursor = "pointer";
      const p = e.features[0].properties as { name: string; linea: string };
      popup.current!.setLngLat(e.lngLat).setHTML(buildStationPopup(p.name, p.linea)).addTo(map.current!);
    });
    map.current.on("mouseleave", "subte-stations", () => {
      map.current!.getCanvas().style.cursor = "";
      popup.current?.remove();
    });

    map.current.addControl(new maplibregl.NavigationControl(), "bottom-right");
    return () => { map.current?.remove(); map.current = null; };
  }, []);

  // ── Sync filter → map dim + comunas highlight ─────────────────────────────
  useEffect(() => {
    if (!loaded || !map.current) return;
    const m = map.current;

    const searchLC = barrioSearch.trim().toLowerCase();
    const matchingNames = searchLC
      ? allNombres.filter((n) => n.toLowerCase().includes(searchLC))
      : [];

    const hasFilter = selectedComunas.length > 0 || matchingNames.length > 0;

    if (!hasFilter) {
      m.setFilter("gap-dim", ["==", 1, 0]);
      m.setFilter("comunas-highlight", ["==", 1, 0]);
      return;
    }

    // Build "show" condition (AND logic: must match both if both active)
    const conditions: maplibregl.FilterSpecification[] = [];
    if (selectedComunas.length > 0)
      conditions.push(["in", ["get", "comuna"], ["literal", selectedComunas]]);
    if (matchingNames.length > 0)
      conditions.push(["in", ["get", "nombre"], ["literal", matchingNames]]);

    const showExpr = (
      conditions.length === 1 ? conditions[0] : ["all", ...conditions]
    ) as maplibregl.FilterSpecification;

    m.setFilter("gap-dim", ["!", showExpr] as maplibregl.FilterSpecification);

    // Highlight selected comunas border
    if (selectedComunas.length > 0) {
      m.setFilter("comunas-highlight", ["in", ["get", "comuna"], ["literal", selectedComunas]]);
    } else {
      m.setFilter("comunas-highlight", ["==", 1, 0]);
    }
  }, [loaded, selectedComunas, barrioSearch, allNombres]);

  // ── Subte visibility ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!loaded || !map.current) return;
    const vis = showSubte ? "visible" : "none";
    ["subte-lines-bg", "subte-lines-fg", "subte-stations"].forEach((id) =>
      map.current!.setLayoutProperty(id, "visibility", vis)
    );
  }, [loaded, showSubte]);

  // ── Label visibility ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!loaded || !map.current) return;
    map.current.setLayoutProperty("barrio-labels", "visibility", showLabels ? "visible" : "none");
  }, [loaded, showLabels]);

  // ── Filter toggle helpers ─────────────────────────────────────────────────
  const toggleComuna = useCallback((c: number) => {
    setSelectedComunas((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  }, []);

  const clearFilters = useCallback(() => {
    setSelectedComunas([]);
    setBarrioSearch("");
  }, []);

  // ── Table sort ────────────────────────────────────────────────────────────
  const handleSort = useCallback((key: SortKey) => {
    if (key === sortKey) setSortAsc((a) => !a);
    else { setSortKey(key); setSortAsc(true); }
  }, [sortKey]);

  // ── Filtered + sorted table rows ─────────────────────────────────────────
  const filteredBarrios = useMemo(() => {
    const searchLC = barrioSearch.trim().toLowerCase();
    return barrios.filter((b) => {
      const comunaOk = selectedComunas.length === 0 || selectedComunas.includes(b.comuna);
      const searchOk = !searchLC || (b.nombre || b.barrio).toLowerCase().includes(searchLC);
      return comunaOk && searchOk;
    });
  }, [barrios, selectedComunas, barrioSearch]);

  const sorted = useMemo(() =>
    [...filteredBarrios].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    }),
    [filteredBarrios, sortKey, sortAsc]
  );

  const highlightBarrio = useCallback((nombre: string) => {
    setSelectedBarrio(nombre);
    map.current?.setFilter("gap-highlight", ["==", ["get", "nombre"], nombre]);
  }, []);

  const filterActive = selectedComunas.length > 0 || barrioSearch.trim().length > 0;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex w-full h-full">

      {/* ── LEFT PANEL ── */}
      <aside className="w-64 flex-shrink-0 h-full bg-[#0f172a] border-r border-white/10 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="px-4 py-3 border-b border-white/10 flex-shrink-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold tracking-[0.2em] text-emerald-400 uppercase">RSI</span>
            <span className="text-white/20">·</span>
            <span className="text-[10px] tracking-widest text-white/35 uppercase">Gap de Valor</span>
          </div>
          <h1 className="text-white text-base font-semibold">CABA · Barrios</h1>
          <p className="text-white/35 text-xs mt-0.5">Precio mercado vs. fundamentals objetivos</p>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">

          {/* Color scale */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Escala de color</p>
            <div className="h-2.5 rounded-sm w-full mb-1.5"
              style={{ background: "linear-gradient(to right, #10b981, #84cc16, #eab308, #f97316, #ef4444, #b91c1c)" }} />
            <div className="flex justify-between text-white/35 text-[10px] mb-2">
              <span>Verde · Barato</span>
              <span>Rojo · Caro</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm bg-[#334155] flex-shrink-0" />
              <span className="text-white/25 text-[10px]">Sin datos (n&lt;6)</span>
            </div>
          </div>

          {/* Layer toggles */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Capas</p>
            <div className="space-y-2">
              {[
                { label: "Líneas de subte", value: showSubte,  set: setShowSubte },
                { label: "Etiquetas barrios", value: showLabels, set: setShowLabels },
              ].map(({ label, value, set }) => (
                <button
                  key={label}
                  onClick={() => set((v) => !v)}
                  className="w-full flex items-center justify-between"
                >
                  <span className="text-white/40 text-[10px]">{label}</span>
                  <div className={`w-7 h-4 rounded-full transition-colors flex-shrink-0 ${value ? "bg-emerald-500" : "bg-white/15"}`}>
                    <div className={`w-3 h-3 rounded-full bg-white mt-0.5 transition-transform ${value ? "translate-x-3.5" : "translate-x-0.5"}`} />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Filters: comunas */}
          <div className="px-4 py-3 border-b border-white/10">
            <div className="flex items-center justify-between mb-2">
              <p className="text-white/35 text-[10px] uppercase tracking-wider">Comunas</p>
              {filterActive && (
                <button onClick={clearFilters}
                  className="text-[9px] text-emerald-400/60 hover:text-emerald-400 transition-colors">
                  Limpiar
                </button>
              )}
            </div>
            <div className="grid grid-cols-5 gap-1">
              {COMUNAS.map((c) => (
                <button
                  key={c}
                  onClick={() => toggleComuna(c)}
                  className={`text-[10px] font-medium py-0.5 rounded transition-colors border ${
                    selectedComunas.includes(c)
                      ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                      : "bg-white/5 border-white/10 text-white/40 hover:border-white/25 hover:text-white/60"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          {/* Filters: barrio search */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Buscar barrio</p>
            <div className="relative">
              <input
                type="text"
                value={barrioSearch}
                onChange={(e) => setBarrioSearch(e.target.value)}
                placeholder="Ej: Palermo…"
                className="w-full bg-white/5 border border-white/10 rounded px-2.5 py-1.5 text-[11px] text-white/70 placeholder-white/25 focus:outline-none focus:border-emerald-500/50 focus:bg-white/8"
              />
              {barrioSearch && (
                <button
                  onClick={() => setBarrioSearch("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 text-xs"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Formula */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Fórmula</p>
            <div className="bg-white/5 rounded px-3 py-2 text-center">
              <p className="text-emerald-400 text-[11px] font-mono font-medium">
                ratio = precio_norm / alpha_score
              </p>
            </div>
            <p className="text-white/25 text-[10px] mt-2 leading-tight">
              precio_norm: min-max 0–100 dentro de la muestra. alpha_score: escala propia 0–100.
            </p>
          </div>

          {/* Methodology brief */}
          <div className="px-4 py-3">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Metodología</p>
            <div className="space-y-1.5">
              <p className="text-white/30 text-[10px] leading-tight">
                Análisis <span className="text-white/50 font-medium">descriptivo</span> de divergencia, no predictivo. OLS r=+0.025, R²=0.001, p=0.902.
              </p>
              <p className="text-white/22 text-[10px] leading-tight">
                992 listings Argenprop · 26 barrios con n≥6.
              </p>
            </div>
          </div>

        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-white/10 flex-shrink-0">
          <p className="text-white/20 text-[10px] text-center">
            Argenprop 2025 · GCBA · OSM · INDEC 2010
          </p>
        </div>
      </aside>

      {/* ── CENTER: Map ── */}
      <div className="flex-1 relative min-w-0">
        <div ref={mapContainer} className="w-full h-full" />
        {!loaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0f172a]">
            <div className="text-white/40 text-sm animate-pulse">Cargando mapa…</div>
          </div>
        )}
      </div>

      {/* ── RIGHT PANEL ── */}
      <aside className="w-80 flex-shrink-0 h-full bg-[#090d16] border-l border-white/10 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="px-4 py-4 border-b border-white/10 flex-shrink-0">
          <p className="text-white/30 text-[10px] uppercase tracking-wider">Gap de Valor · CABA</p>
          <h2 className="text-white text-sm font-semibold mt-0.5">
            {filterActive
              ? `${sorted.length} de ${barrios.length} barrios`
              : `${barrios.length} barrios analizados`}
          </h2>
        </div>

        {/* KPI row */}
        <div className="px-3 py-3 border-b border-white/10 grid grid-cols-3 gap-2 flex-shrink-0">
          {(() => {
            const pool = filterActive ? filteredBarrios : barrios;
            if (!pool.length) return null;
            const best  = pool.reduce((a, b) => ((a.ratio_gap ?? 99) < (b.ratio_gap ?? 99) ? a : b));
            const worst = pool.reduce((a, b) => ((a.ratio_gap ?? 0)  > (b.ratio_gap ?? 0)  ? a : b));
            const avg   = pool.reduce((s, b) => s + (b.ratio_gap ?? 0), 0) / pool.length;
            return (
              <>
                <div className="bg-emerald-500/10 border border-emerald-500/20 rounded px-2 py-2">
                  <p className="text-emerald-400/60 text-[9px] uppercase tracking-wider">Mejor</p>
                  <p className="text-emerald-400 text-sm font-bold">{best.ratio_gap?.toFixed(2)}</p>
                  <p className="text-white/30 text-[9px] truncate">{best.barrio}</p>
                </div>
                <div className="bg-white/5 border border-white/8 rounded px-2 py-2">
                  <p className="text-white/40 text-[9px] uppercase tracking-wider">Promedio</p>
                  <p className="text-white text-sm font-bold">{avg.toFixed(2)}</p>
                  <p className="text-white/30 text-[9px]">{filterActive ? "filtro" : "CABA"}</p>
                </div>
                <div className="bg-red-500/10 border border-red-500/20 rounded px-2 py-2">
                  <p className="text-red-400/60 text-[9px] uppercase tracking-wider">Peor</p>
                  <p className="text-red-400 text-sm font-bold">{worst.ratio_gap?.toFixed(2)}</p>
                  <p className="text-white/30 text-[9px] truncate">{worst.barrio}</p>
                </div>
              </>
            );
          })()}
        </div>

        {/* Tab bar */}
        <div className="flex border-b border-white/10 flex-shrink-0">
          {(["tabla", "casos", "metodologia"] as const).map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 text-[10px] font-medium uppercase tracking-wider transition-colors ${
                activeTab === tab
                  ? "text-emerald-400 border-b-2 border-emerald-400 bg-emerald-400/5"
                  : "text-white/30 hover:text-white/60"
              }`}
            >
              {tab === "tabla" ? "Ranking" : tab === "casos" ? "Casos" : "Metodología"}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto">

          {/* ── TABLA ── */}
          {activeTab === "tabla" && (
            <div>
              <div className="grid grid-cols-4 gap-0 px-3 py-2 border-b border-white/5 sticky top-0 bg-[#090d16]">
                {([
                  ["ratio_gap", "Ratio"],
                  ["alpha_med", "Alpha"],
                  ["usd_m2_med", "USD/m²"],
                  ["n", "n"],
                ] as [SortKey, string][]).map(([key, label]) => (
                  <button key={key} onClick={() => handleSort(key)}
                    className={`text-left text-[9px] uppercase tracking-wider transition-colors flex items-center gap-0.5 ${
                      sortKey === key ? "text-emerald-400" : "text-white/25 hover:text-white/50"
                    }`}
                  >
                    {label}
                    {sortKey === key && <span className="text-[8px]">{sortAsc ? "↑" : "↓"}</span>}
                  </button>
                ))}
              </div>

              {sorted.length === 0 && (
                <p className="text-white/25 text-[10px] text-center py-8">
                  Sin barrios con datos en el filtro activo
                </p>
              )}

              {sorted.map((b) => {
                const rc = (b.ratio_gap ?? 0) < 1.0 ? "#10b981" : (b.ratio_gap ?? 0) < 1.5 ? "#eab308" : "#ef4444";
                const nombre = b.nombre || b.barrio;
                return (
                  <button key={b.barrio} onClick={() => highlightBarrio(nombre)}
                    className={`w-full grid grid-cols-4 gap-0 px-3 py-2 border-b border-white/5 text-left transition-colors ${
                      selectedBarrio === nombre ? "bg-white/8" : "hover:bg-white/5"
                    }`}
                  >
                    <div>
                      <div style={{ color: rc }} className="text-xs font-bold">{b.ratio_gap?.toFixed(2)}</div>
                      <div className="text-white/35 text-[9px] truncate pr-1">{b.barrio}</div>
                    </div>
                    <div className="text-white/60 text-[10px] self-center">{b.alpha_med.toFixed(1)}</div>
                    <div className="text-white/60 text-[10px] self-center">${Math.round(b.usd_m2_med).toLocaleString()}</div>
                    <div className="text-white/40 text-[10px] self-center">{b.n}</div>
                  </button>
                );
              })}
            </div>
          )}

          {/* ── CASOS ── */}
          {activeTab === "casos" && (
            <div className="p-3 space-y-3">
              <p className="text-white/25 text-[10px] leading-tight mb-2">
                Tres casos robustos dentro del rango — excluyen barrios en los extremos exactos de la normalización (precio_norm=0 o 100), cuyos ratios son artefactos de la muestra.
              </p>
              {CASOS.map((c) => (
                <div key={c.barrio} className="rounded-lg border px-3 py-3 space-y-2"
                  style={{ borderColor: `${c.color}30`, background: `${c.color}08` }}>
                  <div className="flex items-center justify-between">
                    <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
                      style={{ color: c.color, background: `${c.color}15`, border: `1px solid ${c.color}30` }}>
                      {c.badge}
                    </span>
                    <span className="text-white/25 text-[10px] font-mono">ratio {c.ratio.toFixed(3)}</span>
                  </div>
                  <div className="text-sm font-semibold" style={{ color: c.color }}>{c.barrio}</div>
                  <p className="text-white/40 text-[10px] leading-relaxed">{c.text}</p>
                </div>
              ))}
              <div className="mt-1 rounded border border-white/8 px-3 py-2.5 space-y-1">
                <p className="text-white/30 text-[9px] font-semibold uppercase tracking-wider">Nota · San Cristóbal</p>
                <p className="text-white/25 text-[10px] leading-relaxed">
                  Tiene el precio mediano más bajo de la muestra ($1.501/m², n=10) pero IQR muy amplio ($1.438–$2.601). Su ratio=0.0 es el ancla mínima del escalado min-max — no un ratio interpretable. Amerita más datos antes de usarlo como ejemplo de oportunidad.
                </p>
              </div>
            </div>
          )}

          {/* ── METODOLOGÍA ── */}
          {activeTab === "metodologia" && (
            <div className="p-3 space-y-4">
              <div className="bg-amber-400/8 border border-amber-400/20 rounded-lg px-3 py-3">
                <p className="text-amber-300 text-[10px] font-semibold uppercase tracking-wider mb-1">
                  Análisis descriptivo · No predictivo
                </p>
                <p className="text-white/40 text-[10px] leading-relaxed">
                  Esta vista muestra dónde el mercado paga más o menos de lo que los fundamentals objetivos sugieren. No es un modelo de predicción de precios.
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-white/35 text-[10px] uppercase tracking-wider">Correlación empírica</p>
                <div className="grid grid-cols-3 gap-2">
                  {[["r", "+0.025"], ["R²", "0.001"], ["p-value", "0.902"]].map(([l, v]) => (
                    <div key={l} className="bg-white/5 rounded px-2 py-2 text-center">
                      <div className="text-white/30 text-[9px] uppercase">{l}</div>
                      <div className="text-white/70 text-xs font-mono font-bold">{v}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <p className="text-white/35 text-[10px] uppercase tracking-wider">Qué mide el Alpha Score</p>
                <div className="space-y-1">
                  {[["Subte","23%"],["POIs/km²","18%"],["Diversidad funcional","18%"],["NBI","10%"],["Espacios verdes","9%"],["Densidad","9%"],["Educación","8%"],["Salud","7%"]].map(([v,w]) => (
                    <div key={v} className="flex items-center justify-between">
                      <span className="text-white/35 text-[10px]">{v}</span>
                      <span className="text-emerald-400/60 text-[10px] font-mono">{w}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-white/35 text-[10px] uppercase tracking-wider">Limitaciones</p>
                {["No causalidad: ratio bajo ≠ precio va a subir","Argenprop sobrerepresenta depts nuevos","Precio de lista ≠ precio de cierre","n<6: 22 barrios sin dato confiable"].map((l) => (
                  <div key={l} className="text-white/25 text-[10px] leading-tight flex gap-1">
                    <span className="text-white/20 flex-shrink-0">·</span>{l}
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </aside>
    </div>
  );
}
