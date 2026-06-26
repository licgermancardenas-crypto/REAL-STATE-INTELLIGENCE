"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import {
  CABARadio,
  GBARadio,
  InteriorRadio,
  SelectedRadio,
  Stats,
  CityConfig,
  CityId,
  COLOR_STOPS,
  CITIES,
} from "./types";
import KPICards from "./KPICards";
import TopZonesTable from "./TopZonesTable";
import ZoneDetail from "./ZoneDetail";
import CitySelector from "./CitySelector";

// ── MapLibre color expressions ────────────────────────────────────────────────

const SCORE_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["get", "alpha_score"],
  ...COLOR_STOPS.flatMap(([v, c]) => [v, c]),
];

const QUINTIL_COLOR_EXPR: maplibregl.ExpressionSpecification = [
  "step",
  ["get", "alpha_quintil"],
  "#1e3a5f",
  2, "#1d4ed8",
  3, "#059669",
  4, "#d97706",
  5, "#dc2626",
];

// ── Layer helpers ─────────────────────────────────────────────────────────────

const CITY_LAYERS = {
  fill:      (id: string) => `${id}-fill`,
  border:    (id: string) => `${id}-border`,
  highlight: (id: string) => `${id}-highlight`,
};

function addCityLayers(
  map: maplibregl.Map,
  cityId: string,
  geojson: string,
  opacity: number,
  colorExpr: maplibregl.ExpressionSpecification,
) {
  if (map.getSource(cityId)) return;
  map.addSource(cityId, { type: "geojson", data: geojson });
  map.addLayer({
    id: CITY_LAYERS.fill(cityId), type: "fill", source: cityId,
    paint: { "fill-color": colorExpr, "fill-opacity": opacity },
  });
  map.addLayer({
    id: CITY_LAYERS.border(cityId), type: "line", source: cityId,
    paint: { "line-color": "#ffffff", "line-width": 0.25, "line-opacity": 0.2 },
  });
  map.addLayer({
    id: CITY_LAYERS.highlight(cityId), type: "fill", source: cityId,
    paint: { "fill-color": "#ffffff", "fill-opacity": 0.15 },
    filter: ["==", ["get", "link"], ""],
  });
}

// ── Stats from GeoJSON features ───────────────────────────────────────────────

function computeStats(features: { properties: CABARadio }[]): Stats {
  const props = features.map((f) => f.properties);
  const scores = props.map((p) => p.alpha_score).sort((a, b) => a - b);
  return {
    count:        scores.length,
    mean:         +(scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1),
    median:       +scores[Math.floor(scores.length / 2)].toFixed(1),
    max:          +scores[scores.length - 1].toFixed(1),
    premiumCount: props.filter((p) => Number(p.alpha_quintil) === 5).length,
    top:          [...props]
      .sort((a, b) => Number(b.alpha_score) - Number(a.alpha_score))
      .slice(0, 10),
  };
}

// ── Popup builders ────────────────────────────────────────────────────────────

const Q_BG: Record<number, string> = {
  1: "#1e3a5f", 2: "#1d4ed8", 3: "#059669", 4: "#d97706", 5: "#dc2626",
};

function buildPopupCABA(p: CABARadio): string {
  const nbiRow = p.pct_sin_nbi != null
    ? `<div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
         <div style="color:#64748b;font-size:10px">% sin NBI</div>
         <div style="font-weight:500">${(Number(p.pct_sin_nbi) * 100).toFixed(1)}%</div>
       </div>`
    : "";
  return `
    <div style="font-family:system-ui;font-size:12px;color:#e2e8f0;min-width:200px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <div style="background:${Q_BG[p.alpha_quintil] ?? "#1e3a5f"};border-radius:6px;padding:6px 10px;font-size:18px;font-weight:700;color:#fff">${p.alpha_score}</div>
        <div>
          <div style="font-weight:600;font-size:13px">Q${p.alpha_quintil} · CABA</div>
          <div style="color:#94a3b8;font-size:10px;font-family:monospace">${p.link}</div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">Subte</div>
          <div style="font-weight:500">${Math.round(Number(p.dist_subte_m))} m</div>
        </div>
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">POIs/km²</div>
          <div style="font-weight:500">${Number(p.poi_total_density).toFixed(0)}</div>
        </div>
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">Pob/km²</div>
          <div style="font-weight:500">${Number(p.densidad_pob).toLocaleString()}</div>
        </div>
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">Diversidad</div>
          <div style="font-weight:500">${Number(p.div_entropy_ex_transporte).toFixed(3)}</div>
        </div>
        ${nbiRow}
      </div>
      <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px;margin-top:4px">
        <div style="color:#64748b;font-size:10px">Subte más cercano</div>
        <div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${p.nearest_subte}</div>
      </div>
    </div>`;
}

function buildPopupGBA(p: GBARadio): string {
  return `
    <div style="font-family:system-ui;font-size:12px;color:#e2e8f0;min-width:200px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <div style="background:${Q_BG[p.alpha_quintil] ?? "#1e3a5f"};border-radius:6px;padding:6px 10px;font-size:18px;font-weight:700;color:#fff">${p.alpha_score}</div>
        <div>
          <div style="font-weight:600;font-size:13px">${p.nombre_partido}</div>
          <div style="color:#94a3b8;font-size:10px">Q${p.alpha_quintil} · <span style="font-family:monospace">${p.link}</span></div>
        </div>
      </div>
      ${p.score_tipo === "parcial"
        ? `<div style="background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.2);border-radius:4px;padding:4px 8px;margin-bottom:6px;font-size:10px;color:#fbbf24">⚠ Score parcial · solo datos censales</div>`
        : `<div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.2);border-radius:4px;padding:4px 8px;margin-bottom:6px;font-size:10px;color:#6ee7b7">✓ Score completo · 7 variables</div>`}
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">Pob/km²</div>
          <div style="font-weight:500">${Number(p.densidad_pob).toLocaleString()}</div>
        </div>
        <div style="background:rgba(255,255,255,0.05);border-radius:4px;padding:4px 6px">
          <div style="color:#64748b;font-size:10px">Población</div>
          <div style="font-weight:500">${Number(p.tot_pob).toLocaleString()}</div>
        </div>
      </div>
    </div>`;
}

function buildPopupInterior(p: InteriorRadio): string {
  return `
    <div style="font-family:system-ui;font-size:12px;color:#e2e8f0;min-width:200px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <div style="background:${Q_BG[p.alpha_quintil] ?? "#1e3a5f"};border-radius:6px;padding:6px 10px;font-size:18px;font-weight:700;color:#fff">${p.alpha_score}</div>
        <div>
          <div style="font-weight:600;font-size:13px">${p.nombre_ciudad ?? p.ciudad}</div>
          <div style="color:#94a3b8;font-size:10px">Q${p.alpha_quintil} · <span style="font-family:monospace">${p.link}</span></div>
        </div>
      </div>
      <div style="background:rgba(100,116,139,0.15);border:1px solid rgba(100,116,139,0.25);border-radius:4px;padding:4px 8px;font-size:10px;color:#94a3b8">
        ⚠ Score proxy geométrico · sin datos POI aún
      </div>
    </div>`;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AlphaMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map          = useRef<maplibregl.Map | null>(null);
  const popup        = useRef<maplibregl.Popup | null>(null);
  const loadedCities = useRef<Set<string>>(new Set());

  const [activeCity, setActiveCity]   = useState<CityConfig>(CITIES[0]);
  const [selected, setSelected]       = useState<SelectedRadio | null>(null);
  const [stats, setStats]             = useState<Stats | null>(null);
  const [colorMode, setColorMode]     = useState<"continuous" | "quintil">("continuous");
  const [mapLoaded, setMapLoaded]     = useState(false);

  // ── Load city GeoJSON + compute stats ────────────────────────────────────────
  const loadCity = useCallback((city: CityConfig) => {
    fetch(city.geojson)
      .then((r) => r.json())
      .then((data) => {
        setStats(computeStats(data.features));
        setSelected(null);

        if (!map.current || !mapLoaded) return;
        const m = map.current;

        // Add layers if not yet loaded
        if (!loadedCities.current.has(city.id)) {
          addCityLayers(m, city.id, city.geojson, 0.72,
            colorMode === "continuous" ? SCORE_COLOR_EXPR : QUINTIL_COLOR_EXPR);
          loadedCities.current.add(city.id);
        }

        // Hide all city fill/border layers, show current
        loadedCities.current.forEach((id) => {
          const vis = id === city.id ? "visible" : "none";
          [CITY_LAYERS.fill(id), CITY_LAYERS.border(id), CITY_LAYERS.highlight(id)].forEach((layer) => {
            if (m.getLayer(layer)) m.setLayoutProperty(layer, "visibility", vis);
          });
        });

        // Fly to city
        m.flyTo({ center: city.center, zoom: city.zoom, duration: 1000 });
      });
  }, [mapLoaded, colorMode]);

  // ── Map init ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style:     "https://tiles.openfreemap.org/styles/dark",
      center:    [-58.44, -34.62],
      zoom:      11.2,
      minZoom:   6,
      maxZoom:   18,
    });

    popup.current = new maplibregl.Popup({
      closeButton: false, closeOnClick: false,
      className: "rsi-popup", maxWidth: "280px",
    });

    map.current.on("load", () => {
      setMapLoaded(true);
    });

    map.current.addControl(new maplibregl.NavigationControl(), "bottom-right");
    return () => { map.current?.remove(); map.current = null; };
  }, []);

  // ── Initial city load (after map ready) ──────────────────────────────────────
  useEffect(() => {
    if (!mapLoaded) return;
    loadCity(CITIES[0]);
    // Pre-load GBA alongside CABA
    addCityLayersFromUrl("gba", "/gba_alpha_scores.geojson", 0.65);
    loadedCities.current.add("gba");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapLoaded]);

  function addCityLayersFromUrl(cityId: string, url: string, opacity: number) {
    if (!map.current || loadedCities.current.has(cityId)) return;
    addCityLayers(map.current, cityId, url, opacity,
      colorMode === "continuous" ? SCORE_COLOR_EXPR : QUINTIL_COLOR_EXPR);
  }

  // ── City switch ───────────────────────────────────────────────────────────────
  const handleCityChange = useCallback((city: CityConfig) => {
    setActiveCity(city);
    setSelected(null);
    popup.current?.remove();
    loadCity(city);
  }, [loadCity]);

  // ── Color mode toggle ─────────────────────────────────────────────────────────
  const applyColorMode = useCallback((mode: "continuous" | "quintil") => {
    if (!map.current || !mapLoaded) return;
    setColorMode(mode);
    const expr = mode === "continuous" ? SCORE_COLOR_EXPR : QUINTIL_COLOR_EXPR;
    loadedCities.current.forEach((id) => {
      const layer = CITY_LAYERS.fill(id);
      if (map.current!.getLayer(layer)) {
        map.current!.setPaintProperty(layer, "fill-color", expr);
      }
    });
  }, [mapLoaded]);

  // ── Click handlers (wired after map load + city layers added) ────────────────
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const m = map.current;

    const onHover = (layerId: string) => {
      m.on("mousemove", layerId, () => { m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", layerId, () => { m.getCanvas().style.cursor = ""; });
    };

    const onClick = (layerId: string, cityId: CityId, builder: (p: Record<string, unknown>) => string) => {
      m.on("click", layerId, (e) => {
        if (!e.features?.length) return;
        const props = e.features[0].properties as Record<string, unknown>;
        setSelected({ ...props, _ciudad: cityId } as unknown as SelectedRadio);
        m.setFilter(CITY_LAYERS.highlight(cityId), ["==", ["get", "link"], (props as { link: string }).link]);
        // Clear other highlights
        loadedCities.current.forEach((id) => {
          if (id !== cityId && m.getLayer(CITY_LAYERS.highlight(id))) {
            m.setFilter(CITY_LAYERS.highlight(id), ["==", ["get", "link"], ""]);
          }
        });
        popup.current!.setLngLat(e.lngLat).setHTML(builder(props)).addTo(m);
      });
    };

    // CABA
    onHover(CITY_LAYERS.fill("caba"));
    onClick(CITY_LAYERS.fill("caba"), "caba", (p) => buildPopupCABA(p as unknown as CABARadio));

    // GBA
    onHover(CITY_LAYERS.fill("gba"));
    onClick(CITY_LAYERS.fill("gba"), "gba", (p) => buildPopupGBA(p as unknown as GBARadio));

    // Interior cities
    (["rosario", "cordoba", "mendoza"] as const).forEach((cityId) => {
      onHover(CITY_LAYERS.fill(cityId));
      onClick(CITY_LAYERS.fill(cityId), cityId, (p) => buildPopupInterior(p as unknown as InteriorRadio));
    });
  }, [mapLoaded]);

  // ── Clear selection ───────────────────────────────────────────────────────────
  const clearSelection = useCallback(() => {
    setSelected(null);
    popup.current?.remove();
    loadedCities.current.forEach((id) => {
      if (map.current?.getLayer(CITY_LAYERS.highlight(id))) {
        map.current.setFilter(CITY_LAYERS.highlight(id), ["==", ["get", "link"], ""]);
      }
    });
  }, []);

  const selectFromTable = useCallback((r: CABARadio) => {
    setSelected({ ...r, _ciudad: "caba" });
    popup.current?.remove();
    if (map.current?.getLayer(CITY_LAYERS.highlight("caba"))) {
      map.current.setFilter(CITY_LAYERS.highlight("caba"), ["==", ["get", "link"], r.link]);
    }
  }, []);

  // ── Methodology text per city ─────────────────────────────────────────────────
  const methodologyRows: { label: string; desc: string; color: string }[] = (() => {
    if (activeCity.id === "caba") return [
      { label: "CABA", color: "#10b981", desc: "8 vars v2: subte (23%), POIs/km² (18%), diversidad (18%), NBI (10%), verdes (9%), densidad (9%), educación (8%), salud (7%)" },
    ];
    if (activeCity.id === "gba") return [
      { label: "GBA", color: "#f59e0b", desc: "3 vars censales: densidad pob. (50%), hogares (30%), ocupación (20%). Sin POIs · no comparable con CABA." },
    ];
    return [
      { label: activeCity.short, color: "#64748b", desc: `Score proxy geométrico: área inversa del radio censal. Score provisional — pipeline con POIs pendiente.` },
    ];
  })();

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="flex w-full h-full">

      {/* ── LEFT: Controls ── */}
      <aside className="w-64 flex-shrink-0 h-full bg-[#0f172a] border-r border-white/10 flex flex-col overflow-hidden">

        {/* Header */}
        <div className="px-4 py-4 border-b border-white/10">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold tracking-[0.2em] text-emerald-400 uppercase">RSI</span>
            <span className="text-white/20">·</span>
            <span className="text-[10px] tracking-widest text-white/35 uppercase">Alpha Score</span>
          </div>
          <h1 className="text-white text-base font-semibold">{activeCity.short}</h1>
          <p className="text-white/35 text-xs mt-0.5">Radio censal</p>
        </div>

        {/* City selector */}
        <CitySelector
          cities={CITIES}
          activeId={activeCity.id}
          onChange={handleCityChange}
        />

        {/* Color mode */}
        <div className="px-4 py-3 border-b border-white/10">
          <div className="flex rounded-md overflow-hidden border border-white/10">
            {(["continuous", "quintil"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => applyColorMode(mode)}
                className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                  colorMode === mode
                    ? "bg-emerald-600 text-white"
                    : "text-white/40 hover:text-white hover:bg-white/5"
                }`}
              >
                {mode === "continuous" ? "Continuo" : "Quintiles"}
              </button>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="px-4 py-3 border-b border-white/10">
          <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Escala de color</p>
          <div
            className="h-2.5 rounded-sm w-full mb-1.5"
            style={{
              background: `linear-gradient(to right, ${COLOR_STOPS.map(([, c]) => c).join(", ")})`,
            }}
          />
          <div className="flex justify-between text-white/35 text-[10px]">
            <span>0 · Bajo</span>
            <span>35 · Medio</span>
            <span>100 · Alto</span>
          </div>
        </div>

        {/* Methodology */}
        <div className="px-4 py-3 border-b border-white/10 flex-1 overflow-y-auto">
          <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Metodología</p>
          <div className="space-y-2">
            {methodologyRows.map(({ label, desc, color }) => (
              <div key={label} className="flex gap-2 items-start">
                <span
                  className="text-[10px] font-bold mt-px flex-shrink-0"
                  style={{ color }}
                >{label}</span>
                <p className="text-white/35 text-[10px] leading-tight">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-white/10 flex-shrink-0">
          <p className="text-white/20 text-[10px] text-center">
            OSM 2025 · GTFS SBASE · Censo INDEC 2010
          </p>
        </div>
      </aside>

      {/* ── CENTER: Map ── */}
      <div className="flex-1 relative min-w-0">
        <div ref={mapContainer} className="w-full h-full" />
        {!mapLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0f172a]">
            <div className="text-white/40 text-sm animate-pulse">Cargando mapa…</div>
          </div>
        )}
      </div>

      {/* ── RIGHT: Executive Dashboard ── */}
      <aside className="w-80 flex-shrink-0 h-full bg-[#090d16] border-l border-white/10 flex flex-col overflow-hidden">
        <div className="px-4 py-4 border-b border-white/10 flex-shrink-0">
          <p className="text-white/30 text-[10px] uppercase tracking-wider">Dashboard Ejecutivo</p>
          <h2 className="text-white text-sm font-semibold mt-0.5">Location Intelligence</h2>
        </div>

        {stats && <KPICards stats={stats} />}

        <div className="px-4 py-2 border-b border-white/10 flex-shrink-0">
          <p className="text-white/20 text-[10px] uppercase tracking-wider">
            {selected ? "Radio seleccionado" : "Ranking"}
          </p>
        </div>

        {selected ? (
          <ZoneDetail selected={selected} onClose={clearSelection} />
        ) : stats ? (
          <TopZonesTable
            radios={stats.top}
            selectedLink={selected ? (selected as { link: string }).link : null}
            onSelect={selectFromTable}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-white/20 text-xs animate-pulse">Cargando…</p>
          </div>
        )}
      </aside>
    </div>
  );
}
