"use client";

import { useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api } from "@/lib/api";

const CITY_DEFAULTS: Record<string, [number, number, number]> = {
  caba: [-58.3816, -34.6037, 12],
  rosario: [-60.6505, -32.9442, 12],
  cordoba: [-64.1811, -31.4135, 12],
  mendoza: [-68.8458, -32.8895, 12],
};

export function AlphaMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const params = useSearchParams();
  const city = params.get("city") ?? "caba";

  const { data: alphaGeoJson } = useQuery({
    queryKey: ["alpha-map", city],
    queryFn: () => api.get(`/api/alpha/map/${city}`).then((r) => r.data),
  });

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const [lng, lat, zoom] = CITY_DEFAULTS[city] ?? CITY_DEFAULTS.caba;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [lng, lat],
      zoom,
    });

    map.current.addControl(new maplibregl.NavigationControl(), "top-right");

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Fly to city on change
  useEffect(() => {
    if (!map.current) return;
    const [lng, lat, zoom] = CITY_DEFAULTS[city] ?? CITY_DEFAULTS.caba;
    map.current.flyTo({ center: [lng, lat], zoom, duration: 1200 });
  }, [city]);

  // Add/update alpha heatmap layer
  useEffect(() => {
    if (!map.current || !alphaGeoJson?.features?.length) return;

    const sourceId = "alpha-zones";
    const layerId = "alpha-fill";

    if (map.current.getSource(sourceId)) {
      (map.current.getSource(sourceId) as maplibregl.GeoJSONSource).setData(alphaGeoJson);
    } else {
      map.current.addSource(sourceId, { type: "geojson", data: alphaGeoJson });
      map.current.addLayer({
        id: layerId,
        type: "fill",
        source: sourceId,
        paint: {
          "fill-color": [
            "interpolate", ["linear"],
            ["get", "alpha_score"],
            0, "#ef4444",
            50, "#f59e0b",
            100, "#10b981",
          ],
          "fill-opacity": 0.55,
        },
      });
    }
  }, [alphaGeoJson]);

  return <div ref={mapContainer} className="w-full h-full" />;
}
