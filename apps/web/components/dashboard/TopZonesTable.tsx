"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function TopZonesTable() {
  const params = useSearchParams();
  const city = params.get("city") ?? "caba";

  const { data: zones } = useQuery({
    queryKey: ["zones", city, "top"],
    queryFn: () =>
      api.get(`/api/zones/${city}?limit=10`).then((r) =>
        [...r.data].sort((a: { alpha_score: number }, b: { alpha_score: number }) => b.alpha_score - a.alpha_score)
      ),
  });

  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
        Top Zonas Alpha
      </span>
      {zones?.length === 0 && (
        <p className="text-xs text-gray-600">Sin datos aún</p>
      )}
      {zones?.map((z: { zone_id: string; name: string; alpha_score: number }) => (
        <div key={z.zone_id} className="flex items-center justify-between">
          <span className="text-sm text-gray-300 truncate">{z.name}</span>
          <span
            className={`text-xs font-mono font-bold ${
              z.alpha_score >= 70
                ? "text-alpha-high"
                : z.alpha_score >= 40
                ? "text-alpha-mid"
                : "text-alpha-low"
            }`}
          >
            {z.alpha_score.toFixed(0)}
          </span>
        </div>
      ))}
    </div>
  );
}
