"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

interface Kpi {
  label: string;
  value: string;
  delta?: string;
  positive?: boolean;
}

export function KpiGrid() {
  const params = useSearchParams();
  const city = params.get("city") ?? "caba";

  const { data: zones } = useQuery({
    queryKey: ["zones", city],
    queryFn: () => api.get(`/api/zones/${city}`).then((r) => r.data),
  });

  const kpis: Kpi[] = [
    { label: "Zonas analizadas", value: zones?.length?.toString() ?? "—" },
    { label: "Alpha Score promedio", value: "—", delta: "—" },
    { label: "Precio promedio USD/m²", value: "—", delta: "—" },
    { label: "Zonas oportunidad", value: "—", positive: true },
  ];

  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">KPIs</span>
      {kpis.map((k) => (
        <div key={k.label} className="bg-gray-900 rounded-lg p-3">
          <p className="text-xs text-gray-500">{k.label}</p>
          <p className="text-xl font-bold text-white mt-1">{k.value}</p>
          {k.delta && (
            <p className={`text-xs mt-0.5 ${k.positive ? "text-alpha-high" : "text-gray-400"}`}>
              {k.delta}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
