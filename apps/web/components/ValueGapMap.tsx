"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import maplibregl from "maplibre-gl";
import RangeSlider from "./RangeSlider";

// ── Types ─────────────────────────────────────────────────────────────────────

interface BarrioGap {
  barrio:     string;
  nombre:     string;
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

const LINEAS: { id: string; colour: string }[] = [
  { id: "A", colour: "#1CA4CB" },
  { id: "B", colour: "#C20924" },
  { id: "C", colour: "#003EA1" },
  { id: "D", colour: "#217861" },
  { id: "E", colour: "#6B297E" },
  { id: "H", colour: "#F4CC21" },
];

// Haversine distance in metres
function haversine(lon1: number, lat1: number, lon2: number, lat2: number): number {
  const R = 6_371_000;
  const toRad = (v: number) => (v * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Approximate centroid of a GeoJSON polygon (average of exterior ring coords)
function polygonCentroid(geom: GeoJSON.Geometry): [number, number] | null {
  let ring: number[][] | null = null;
  if (geom.type === "Polygon") ring = geom.coordinates[0];
  else if (geom.type === "MultiPolygon") ring = geom.coordinates[0][0];
  if (!ring || ring.length === 0) return null;
  const lon = ring.reduce((s, c) => s + c[0], 0) / ring.length;
  const lat = ring.reduce((s, c) => s + c[1], 0) / ring.length;
  return [lon, lat];
}

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

// ── Casos destacados ───────────────────────────────────────────────────────────

const CASOS = [
  {
    barrio: "San Nicolas", badge: "Mejor Valor", color: "#10b981", ratio: 0.722,
    text: "Alpha p85 (accesibilidad top), precio p8 ($2.115/m²). El mercado no refleja los fundamentals. Centro histórico con alta conectividad pero baja demanda residencial premium.",
  },
  {
    barrio: "Belgrano", badge: "Equilibrado", color: "#eab308", ratio: 1.542,
    text: "Alpha p92 (uno de los más accesibles), precio p58. Ratio 1.54 indica prima moderada y razonable. Buen punto de referencia.",
  },
  {
    barrio: "Villa Del Parque", badge: "Mayor Prima", color: "#ef4444", ratio: 2.938,
    text: "Alpha p8 (accesibilidad baja), precio p50 ($2.706/m²). Ratio 2.94, el más alto de CABA. La demanda paga precio residencial que el modelo objetivo no justifica.",
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ValueGapMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map          = useRef<maplibregl.Map | null>(null);
  const popup        = useRef<maplibregl.Popup | null>(null);
  // Flag to distinguish barrio-click from background-click
  const clickedFeature = useRef(false);

  const [barrios, setBarrios]               = useState<BarrioGap[]>([]);
  const [allNombres, setAllNombres]         = useState<string[]>([]);
  const [loaded, setLoaded]                 = useState(false);
  const [sortKey, setSortKey]               = useState<SortKey>("ratio_gap");
  const [sortAsc, setSortAsc]               = useState(true);
  const [selectedBarrio, setSelectedBarrio] = useState<string | null>(null);
  const [activeTab, setActiveTab]           = useState<"tabla" | "casos" | "metodologia">("tabla");

  // Existing filters
  const [selectedComunas, setSelectedComunas]   = useState<number[]>([]);
  const [barrioListFilter, setBarrioListFilter] = useState(""); // filters the barrio button list only — not the map
  const [showSubte, setShowSubte]               = useState(true);
  const [showLabels, setShowLabels]             = useState(false);

  // ── NEW state ─────────────────────────────────────────────────────────────
  const [focusedBarrio, setFocusedBarrio]   = useState<string | null>(null);
  const [activeLineas, setActiveLineas]     = useState<string[]>([]);
  const [ratioRange, setRatioRange]         = useState<[number, number]>([0, 4]);
  const [ratioMinMax, setRatioMinMax]       = useState<[number, number]>([0, 4]);
  // barrio nombre → [lon, lat] centroid, used for flyTo
  const barrioCentroids = useRef<Record<string, [number, number]>>({});
  // linea id → barrio nombres within 600m of any station on that line
  // NOTE: uses barrio centroid (not full polygon), so large barrios may have
  // false positives/negatives at their edges — accepted approximation.
  const lineaBarrios = useRef<Record<string, string[]>>({});

  // ── Load GeoJSON + pre-compute derived data ────────────────────────────────
  useEffect(() => {
    Promise.all([
      fetch("/value_gap_caba.geojson").then((r) => r.json()),
      fetch("/subte_stations_caba.geojson").then((r) => r.json()),
    ]).then(([gapData, stationsData]) => {
      const all: BarrioGap[] = gapData.features.map(
        (f: { properties: BarrioGap }) => f.properties,
      );
      setAllNombres(all.map((p) => p.nombre || p.barrio));
      setBarrios(all.filter((p) => p.confiable && p.ratio_gap != null));

      // Ratio min/max from confiable barrios with data
      const ratios = all
        .filter((p) => p.confiable && p.ratio_gap != null)
        .map((p) => p.ratio_gap as number);
      if (ratios.length) {
        const lo = Math.floor(Math.min(...ratios) * 10) / 10;
        const hi = Math.ceil(Math.max(...ratios) * 10) / 10;
        setRatioMinMax([lo, hi]);
        setRatioRange([lo, hi]);
      }

      // Centroid per barrio (for flyTo)
      gapData.features.forEach((f: { properties: BarrioGap; geometry: GeoJSON.Geometry }) => {
        const nombre = f.properties.nombre || f.properties.barrio;
        const c = polygonCentroid(f.geometry);
        if (c) barrioCentroids.current[nombre] = c;
      });

      // Station positions by linea (for proximity filter)
      const stationsByLinea: Record<string, [number, number][]> = {};
      stationsData.features.forEach((f: { properties: { linea: string }; geometry: { coordinates: [number, number] } }) => {
        const linea = f.properties.linea;
        if (!linea) return;
        if (!stationsByLinea[linea]) stationsByLinea[linea] = [];
        stationsByLinea[linea].push(f.geometry.coordinates);
      });

      // Pre-compute which barrios are within 600m of each line
      // NOTE: proximity is measured from the barrio's centroid, not its full polygon.
      // Large barrios may show false positives/negatives at their edges — accepted approximation.
      const PROXIMITY_M = 600;
      const built: Record<string, string[]> = {};
      LINEAS.forEach(({ id }) => {
        const stations = stationsByLinea[id] || [];
        built[id] = gapData.features
          .filter((f: { properties: BarrioGap; geometry: GeoJSON.Geometry }) => {
            const c = polygonCentroid(f.geometry);
            if (!c) return false;
            return stations.some(
              ([slon, slat]) => haversine(c[0], c[1], slon, slat) <= PROXIMITY_M,
            );
          })
          .map((f: { properties: BarrioGap }) => f.properties.nombre || f.properties.barrio);
      });
      lineaBarrios.current = built;
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

      // Gap choropleth
      m.addSource("gap", { type: "geojson", data: "/value_gap_caba.geojson" });
      m.addLayer({ id: "gap-fill", type: "fill", source: "gap",
        paint: { "fill-color": GAP_COLOR_EXPR, "fill-opacity": 0.80 } });
      m.addLayer({ id: "gap-border", type: "line", source: "gap",
        paint: { "line-color": "#ffffff", "line-width": 0.5, "line-opacity": 0.18 } });

      // Unified dim overlay — starts hidden, fades in when any filter is active.
      // fill-opacity-transition enables smooth CSS-style fading.
      m.addLayer({ id: "gap-dim", type: "fill", source: "gap",
        paint: {
          "fill-color": "#0a0f1e",
          "fill-opacity": 0,
          "fill-opacity-transition": { duration: 250, delay: 0 },
        },
        filter: ["==", 1, 0],
      });

      // Comunas borders + highlight
      m.addSource("comunas", { type: "geojson", data: "/comunas_caba.geojson" });
      m.addLayer({ id: "comunas-border", type: "line", source: "comunas",
        paint: { "line-color": "#94a3b8", "line-width": 1.5, "line-opacity": 0.35, "line-dasharray": [4, 3] } });
      m.addLayer({ id: "comunas-highlight", type: "line", source: "comunas",
        paint: { "line-color": "#ffffff", "line-width": 2.5, "line-opacity": 0.75 },
        filter: ["==", 1, 0] });

      // Subte lines
      m.addSource("subte-lines", { type: "geojson", data: "/subte_lines_caba.geojson" });
      m.addLayer({ id: "subte-lines-bg", type: "line", source: "subte-lines",
        paint: { "line-color": "#000000", "line-width": 4, "line-opacity": 0.5 } });
      m.addLayer({ id: "subte-lines-fg", type: "line", source: "subte-lines",
        paint: { "line-color": ["get", "colour"], "line-width": 2.5, "line-opacity": 0.95 } });

      // Subte stations
      m.addSource("subte-stations", { type: "geojson", data: "/subte_stations_caba.geojson" });
      m.addLayer({ id: "subte-stations", type: "circle", source: "subte-stations",
        paint: {
          "circle-radius": 4,
          "circle-color": ["get", "colour"],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.95,
        } });

      // Barrio labels
      m.addLayer({ id: "barrio-labels", type: "symbol", source: "gap",
        layout: {
          "text-field": ["get", "nombre"],
          "text-size": 9, "text-anchor": "center",
          "text-allow-overlap": false, "text-max-width": 8,
          "visibility": "none",
        },
        paint: {
          "text-color": "#e2e8f0", "text-opacity": 0.75,
          "text-halo-color": "#0a0f1e", "text-halo-width": 1.5,
        } });

      // Selection highlight ring
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

    // Barrio click → focus + flyTo
    map.current.on("click", "gap-fill", (e) => {
      if (!e.features?.length) return;
      clickedFeature.current = true;
      const p = e.features[0].properties as BarrioGap;
      const nombre = p.nombre || p.barrio;
      setSelectedBarrio(nombre);
      setFocusedBarrio(nombre);
      map.current!.setFilter("gap-highlight", ["==", ["get", "nombre"], nombre]);

      const center = barrioCentroids.current[nombre];
      if (center) {
        map.current!.flyTo({ center, zoom: 13.5, duration: 600, essential: true });
      }
    });

    // Click on map background → clear focus, reset zoom
    map.current.on("click", () => {
      if (clickedFeature.current) {
        clickedFeature.current = false;
        return;
      }
      setFocusedBarrio(null);
      setSelectedBarrio(null);
      popup.current?.remove();
      map.current?.setFilter("gap-highlight", ["==", ["get", "nombre"], ""]);
      map.current?.flyTo({ center: [-58.44, -34.62], zoom: 11.2, duration: 700, essential: true });
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

  // ── Unified dim + highlight sync ───────────────────────────────────────────
  useEffect(() => {
    if (!loaded || !map.current) return;
    const m = map.current;

    const [lo, hi] = ratioRange;
    const ratioActive = lo > ratioMinMax[0] + 0.001 || hi < ratioMinMax[1] - 0.001;

    // Each entry is a MapLibre condition for barrios that SHOULD be shown (not dimmed).
    // All conditions combine as AND — a barrio passes only if it satisfies every active filter.
    const conditions: maplibregl.FilterSpecification[] = [];

    // Comunas: native MapLibre expression (covers all features including non-confiable)
    if (selectedComunas.length > 0) {
      conditions.push(["in", ["get", "comuna"], ["literal", selectedComunas]] as maplibregl.FilterSpecification);
    }

    // Subte line proximity: pre-computed centroid-based sets → literal name list
    if (activeLineas.length > 0) {
      const nearby = [...new Set(activeLineas.flatMap((l) => lineaBarrios.current[l] || []))];
      conditions.push(["in", ["get", "nombre"], ["literal", nearby]] as maplibregl.FilterSpecification);
    }

    // Focused barrio (from map click or table row click)
    if (focusedBarrio) {
      conditions.push(["==", ["get", "nombre"], focusedBarrio] as maplibregl.FilterSpecification);
    }

    // Ratio range: native comparison — null values fail >= and are naturally excluded
    if (ratioActive) {
      conditions.push([">=", ["get", "ratio_gap"], lo] as maplibregl.FilterSpecification);
      conditions.push(["<=", ["get", "ratio_gap"], hi] as maplibregl.FilterSpecification);
    }

    if (conditions.length === 0) {
      m.setPaintProperty("gap-dim", "fill-opacity", 0);
      m.setFilter("comunas-highlight", ["==", 1, 0]);
      return;
    }

    const showExpr = (
      conditions.length === 1 ? conditions[0] : ["all", ...conditions]
    ) as maplibregl.FilterSpecification;

    m.setFilter("gap-dim", ["!", showExpr] as maplibregl.FilterSpecification);
    m.setPaintProperty("gap-dim", "fill-opacity", 0.75);

    if (selectedComunas.length > 0) {
      m.setFilter("comunas-highlight", ["in", ["get", "comuna"], ["literal", selectedComunas]] as maplibregl.FilterSpecification);
    } else {
      m.setFilter("comunas-highlight", ["==", 1, 0]);
    }
  }, [loaded, selectedComunas, activeLineas, ratioRange, ratioMinMax, focusedBarrio]);

  // ── Subte line highlight — selected line at full opacity, others dimmed ──────
  useEffect(() => {
    if (!loaded || !map.current) return;
    const m = map.current;
    if (activeLineas.length === 0) {
      m.setPaintProperty("subte-lines-fg", "line-opacity", 0.95);
      m.setPaintProperty("subte-lines-bg", "line-opacity", 0.5);
      m.setPaintProperty("subte-stations", "circle-opacity", 0.95);
      m.setPaintProperty("subte-stations", "circle-stroke-opacity", 1.0);
    } else {
      const sel: maplibregl.ExpressionSpecification = ["in", ["get", "linea"], ["literal", activeLineas]];
      m.setPaintProperty("subte-lines-fg", "line-opacity", ["case", sel, 0.95, 0.08]);
      m.setPaintProperty("subte-lines-bg", "line-opacity", ["case", sel, 0.55, 0.05]);
      m.setPaintProperty("subte-stations", "circle-opacity", ["case", sel, 0.95, 0.06]);
      m.setPaintProperty("subte-stations", "circle-stroke-opacity", ["case", sel, 1.0, 0.04]);
    }
  }, [loaded, activeLineas]);

  // ── Subte visibility ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!loaded || !map.current) return;
    const vis = showSubte ? "visible" : "none";
    ["subte-lines-bg", "subte-lines-fg", "subte-stations"].forEach((id) =>
      map.current!.setLayoutProperty(id, "visibility", vis),
    );
  }, [loaded, showSubte]);

  // ── Label visibility ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!loaded || !map.current) return;
    map.current.setLayoutProperty("barrio-labels", "visibility", showLabels ? "visible" : "none");
  }, [loaded, showLabels]);

  // ── Interaction helpers ───────────────────────────────────────────────────

  const toggleComuna = useCallback((c: number) => {
    setSelectedComunas((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c],
    );
  }, []);

  const toggleLinea = useCallback((id: string) => {
    setActiveLineas((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  // Fly to barrio from table row click + highlight
  const highlightBarrio = useCallback((nombre: string) => {
    setSelectedBarrio(nombre);
    setFocusedBarrio(nombre);
    map.current?.setFilter("gap-highlight", ["==", ["get", "nombre"], nombre]);
    const center = barrioCentroids.current[nombre];
    if (center && map.current) {
      map.current.flyTo({ center, zoom: 13.5, duration: 600, essential: true });
    }
  }, []);

  const clearAll = useCallback(() => {
    setSelectedComunas([]);
    setBarrioListFilter("");
    setActiveLineas([]);
    setRatioRange(ratioMinMax);
    setFocusedBarrio(null);
    setSelectedBarrio(null);
    popup.current?.remove();
    map.current?.setFilter("gap-highlight", ["==", ["get", "nombre"], ""]);
    map.current?.flyTo({ center: [-58.44, -34.62], zoom: 11.2, duration: 700, essential: true });
  }, [ratioMinMax]);

  const handleSort = useCallback((key: SortKey) => {
    if (key === sortKey) setSortAsc((a) => !a);
    else { setSortKey(key); setSortAsc(true); }
  }, [sortKey]);

  // ── Filtered + sorted table rows ──────────────────────────────────────────
  // Table filters: comunas + linea + ratio (focus is map-navigation only, not a table filter)
  const filteredBarrios = useMemo(() => {
    const [lo, hi] = ratioRange;
    const lineaSet = activeLineas.length > 0
      ? new Set(activeLineas.flatMap((l) => lineaBarrios.current[l] || []))
      : null;
    return barrios.filter((b) => {
      const nombre = b.nombre || b.barrio;
      if (selectedComunas.length > 0 && !selectedComunas.includes(b.comuna)) return false;
      if (lineaSet && !lineaSet.has(nombre)) return false;
      if (b.ratio_gap == null) return false;
      if (b.ratio_gap < lo || b.ratio_gap > hi) return false;
      return true;
    });
  }, [barrios, selectedComunas, activeLineas, ratioRange]);

  const sorted = useMemo(() =>
    [...filteredBarrios].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      return sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    }),
    [filteredBarrios, sortKey, sortAsc],
  );

  const filterActive =
    selectedComunas.length > 0 ||
    activeLineas.length > 0 ||
    focusedBarrio !== null ||
    ratioRange[0] > ratioMinMax[0] + 0.001 ||
    ratioRange[1] < ratioMinMax[1] - 0.001;

  // Sorted list of barrio name buttons, filtered by the local search field
  const visibleBarrioButtons = useMemo(() => {
    const f = barrioListFilter.trim().toLowerCase();
    return [...allNombres].sort().filter((n) => !f || n.toLowerCase().includes(f));
  }, [allNombres, barrioListFilter]);

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
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-white text-base font-semibold">CABA · Barrios</h1>
              <p className="text-white/35 text-xs mt-0.5">Precio mercado vs. fundamentals objetivos</p>
            </div>
            {filterActive && (
              <button
                onClick={clearAll}
                className="text-[9px] text-emerald-400/70 hover:text-emerald-400 transition-colors flex-shrink-0 ml-2"
              >
                Reset
              </button>
            )}
          </div>
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
                { label: "Líneas de subte",   value: showSubte,  set: setShowSubte },
                { label: "Etiquetas barrios", value: showLabels, set: setShowLabels },
              ].map(({ label, value, set }) => (
                <button key={label} onClick={() => set((v) => !v)}
                  className="w-full flex items-center justify-between">
                  <span className="text-white/40 text-[10px]">{label}</span>
                  <div className={`w-7 h-4 rounded-full transition-colors flex-shrink-0 ${value ? "bg-emerald-500" : "bg-white/15"}`}>
                    <div className={`w-3 h-3 rounded-full bg-white mt-0.5 transition-transform ${value ? "translate-x-3.5" : "translate-x-0.5"}`} />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Filtro línea de subte */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Línea de subte</p>
            <div className="flex flex-wrap gap-1">
              {LINEAS.map(({ id, colour }) => {
                const active = activeLineas.includes(id);
                return (
                  <button
                    key={id}
                    onClick={() => toggleLinea(id)}
                    className={`px-2.5 py-1 rounded text-[11px] font-bold transition-all border ${
                      active ? "text-white" : "text-white/35 hover:text-white/60"
                    }`}
                    style={active
                      ? { backgroundColor: colour + "33", borderColor: colour + "88", color: colour }
                      : { borderColor: "rgba(255,255,255,0.1)", backgroundColor: "transparent" }
                    }
                  >
                    {id}
                  </button>
                );
              })}
            </div>
            {activeLineas.length > 0 && (
              <p className="text-white/25 text-[9px] mt-1.5 leading-tight">
                Barrios con centroide a ≤600m de la línea
              </p>
            )}
          </div>

          {/* Slider rango de ratio */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-1">Rango de ratio</p>
            <RangeSlider
              min={ratioMinMax[0]}
              max={ratioMinMax[1]}
              value={ratioRange}
              step={0.05}
              onChange={setRatioRange}
            />
          </div>

          {/* Filtros: comunas */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Comunas</p>
            <div className="grid grid-cols-5 gap-1">
              {COMUNAS.map((c) => (
                <button key={c} onClick={() => toggleComuna(c)}
                  className={`text-[10px] font-medium py-0.5 rounded transition-colors border ${
                    selectedComunas.includes(c)
                      ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                      : "bg-white/5 border-white/10 text-white/40 hover:border-white/25 hover:text-white/60"
                  }`}>
                  {c}
                </button>
              ))}
            </div>
          </div>

          {/* Filtros: barrio buttons */}
          <div className="px-4 py-3 border-b border-white/10">
            <div className="flex items-center justify-between mb-2">
              <p className="text-white/35 text-[10px] uppercase tracking-wider">Barrios</p>
              {focusedBarrio && (
                <button
                  onClick={() => { setFocusedBarrio(null); setSelectedBarrio(null); map.current?.setFilter("gap-highlight", ["==", ["get", "nombre"], ""]); map.current?.flyTo({ center: [-58.44, -34.62], zoom: 11.2, duration: 700, essential: true }); }}
                  className="text-[9px] text-white/30 hover:text-white/60 transition-colors"
                >
                  ✕ deselect
                </button>
              )}
            </div>
            {/* Local search — filters the button list only, not the map */}
            <div className="relative mb-2">
              <input
                type="text" value={barrioListFilter}
                onChange={(e) => setBarrioListFilter(e.target.value)}
                placeholder="Filtrar lista…"
                className="w-full bg-white/5 border border-white/10 rounded px-2.5 py-1 text-[10px] text-white/60 placeholder-white/20 focus:outline-none focus:border-white/25"
              />
              {barrioListFilter && (
                <button onClick={() => setBarrioListFilter("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-white/25 hover:text-white/50 text-[10px]">✕</button>
              )}
            </div>
            <div className="flex flex-wrap gap-1 max-h-36 overflow-y-auto pr-0.5">
              {visibleBarrioButtons.map((nombre) => {
                const isFocused = focusedBarrio === nombre;
                return (
                  <button
                    key={nombre}
                    onClick={() => highlightBarrio(nombre)}
                    className={`px-2 py-0.5 rounded text-[10px] font-medium transition-all border ${
                      isFocused
                        ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                        : "bg-white/5 border-white/10 text-white/40 hover:border-white/25 hover:text-white/70"
                    }`}
                  >
                    {nombre}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Formula */}
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Fórmula</p>
            <div className="bg-white/5 rounded px-3 py-2 text-center">
              <p className="text-emerald-400 text-[11px] font-mono font-medium">ratio = precio_norm / alpha_score</p>
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
        {/* Reset focus button — appears when a barrio is focused */}
        {focusedBarrio && (
          <button
            onClick={clearAll}
            className="absolute top-3 left-1/2 -translate-x-1/2 bg-[#1e293b]/90 border border-white/15 text-white/70 text-[11px] px-3 py-1.5 rounded-full backdrop-blur-sm hover:text-white hover:border-white/30 transition-all"
          >
            ✕ {focusedBarrio} — limpiar foco
          </button>
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
              }`}>
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
                {([["ratio_gap","Ratio"],["alpha_med","Alpha"],["usd_m2_med","USD/m²"],["n","n"]] as [SortKey, string][]).map(([key, label]) => (
                  <button key={key} onClick={() => handleSort(key)}
                    className={`text-left text-[9px] uppercase tracking-wider transition-colors flex items-center gap-0.5 ${
                      sortKey === key ? "text-emerald-400" : "text-white/25 hover:text-white/50"
                    }`}>
                    {label}
                    {sortKey === key && <span className="text-[8px]">{sortAsc ? "↑" : "↓"}</span>}
                  </button>
                ))}
              </div>

              {sorted.length === 0 && (
                <p className="text-white/25 text-[10px] text-center py-8">Sin barrios en el filtro activo</p>
              )}

              {sorted.map((b) => {
                const rc = (b.ratio_gap ?? 0) < 1.0 ? "#10b981" : (b.ratio_gap ?? 0) < 1.5 ? "#eab308" : "#ef4444";
                const nombre = b.nombre || b.barrio;
                const isFocused = selectedBarrio === nombre;
                return (
                  <button key={b.barrio} onClick={() => highlightBarrio(nombre)}
                    className={`w-full grid grid-cols-4 gap-0 px-3 py-2 border-b border-white/5 text-left transition-all duration-200 ${
                      isFocused ? "bg-white/10" : "hover:bg-white/5"
                    }`}>
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
                Tres casos robustos dentro del rango — excluyen barrios en los extremos exactos de la normalización (precio_norm=0 o 100).
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
                  Precio mediano más bajo ($1.501/m², n=10) pero IQR muy amplio. Su ratio=0.0 es el ancla mínima del escalado min-max — no un ratio interpretable.
                </p>
              </div>
            </div>
          )}

          {/* ── METODOLOGÍA ── */}
          {activeTab === "metodologia" && (
            <div className="p-3 space-y-4">
              <div className="bg-amber-400/8 border border-amber-400/20 rounded-lg px-3 py-3">
                <p className="text-amber-300 text-[10px] font-semibold uppercase tracking-wider mb-1">Análisis descriptivo · No predictivo</p>
                <p className="text-white/40 text-[10px] leading-relaxed">
                  Esta vista muestra dónde el mercado paga más o menos de lo que los fundamentals objetivos sugieren.
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-white/35 text-[10px] uppercase tracking-wider">Correlación empírica</p>
                <div className="grid grid-cols-3 gap-2">
                  {[["r","+0.025"],["R²","0.001"],["p-value","0.902"]].map(([l,v]) => (
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
