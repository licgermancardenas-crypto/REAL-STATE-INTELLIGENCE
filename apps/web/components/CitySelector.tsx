"use client";

import { CityConfig, CityId } from "./types";

const SCORE_META: Record<string, { label: string; color: string; dot: string }> = {
  completo:   { label: "8 vars",  color: "text-emerald-400", dot: "bg-emerald-400" },
  parcial:    { label: "3 vars",  color: "text-amber-400",   dot: "bg-amber-400" },
  geometrico: { label: "proxy",   color: "text-slate-400",   dot: "bg-slate-400" },
};

interface Props {
  cities: CityConfig[];
  activeId: CityId;
  onChange: (city: CityConfig) => void;
}

export default function CitySelector({ cities, activeId, onChange }: Props) {
  return (
    <div className="px-4 py-3 border-b border-white/10">
      <p className="text-white/35 text-[10px] uppercase tracking-wider mb-2">Ciudad</p>
      <div className="space-y-1">
        {cities.map((city) => {
          const meta = SCORE_META[city.scoreType];
          const active = city.id === activeId;
          return (
            <button
              key={city.id}
              onClick={() => onChange(city)}
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded text-left transition-colors ${
                active
                  ? "bg-emerald-500/15 border border-emerald-500/25"
                  : "hover:bg-white/5 border border-transparent"
              }`}
            >
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${meta.dot}`} />
                <span className={`text-[11px] font-medium ${active ? "text-white" : "text-white/50"}`}>
                  {city.short}
                </span>
              </div>
              <span className={`text-[9px] font-mono ${meta.color}`}>{meta.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
