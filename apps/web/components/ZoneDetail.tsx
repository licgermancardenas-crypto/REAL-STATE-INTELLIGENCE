import { CABARadio, GBARadio, InteriorRadio, SelectedRadio, scoreColor, scoreLabel } from "./types";

// Weight = % contribution to Alpha Score (as per methodology v2)
// Bar width normalized: max driver (23%) fills 100% of track
const CABA_DRIVERS: {
  label: string;
  weight: number;
  color: string;
  getValue: (r: CABARadio) => string;
  hasData: boolean;
}[] = [
  {
    label: "Subte",
    weight: 23,
    color: "#6366f1",
    getValue: (r) => `${Math.round(Number(r.dist_subte_m))} m`,
    hasData: true,
  },
  {
    label: "POIs/km²",
    weight: 18,
    color: "#0ea5e9",
    getValue: (r) => `${Number(r.poi_total_density).toFixed(0)}`,
    hasData: true,
  },
  {
    label: "Diversidad",
    weight: 18,
    color: "#10b981",
    getValue: (r) => `${Number(r.div_entropy_ex_transporte).toFixed(3)}`,
    hasData: true,
  },
  {
    label: "NBI",
    weight: 10,
    color: "#f59e0b",
    getValue: (r) =>
      r.pct_sin_nbi != null
        ? `${(Number(r.pct_sin_nbi) * 100).toFixed(1)}%`
        : "—",
    hasData: true,
  },
  {
    label: "Densidad pob.",
    weight: 9,
    color: "#8b5cf6",
    getValue: (r) => `${Number(r.densidad_pob).toLocaleString()}/km²`,
    hasData: true,
  },
  {
    label: "Verdes",
    weight: 9,
    color: "#22c55e",
    getValue: () => "pendiente",
    hasData: false,
  },
  {
    label: "Educación",
    weight: 8,
    color: "#ec4899",
    getValue: () => "pendiente",
    hasData: false,
  },
  {
    label: "Salud",
    weight: 7,
    color: "#ef4444",
    getValue: () => "pendiente",
    hasData: false,
  },
];

const MAX_WEIGHT = 23; // subte is highest weight driver

export default function ZoneDetail({
  selected,
  onClose,
}: {
  selected: SelectedRadio;
  onClose: () => void;
}) {
  const isGBA      = selected._ciudad === "gba";
  const isInterior = !["caba", "gba"].includes(selected._ciudad);
  const score      = Number(selected.alpha_score);

  return (
    <div className="flex flex-col flex-1 min-h-0">

      {/* Header */}
      <div className="px-4 py-2.5 border-b border-white/10 flex items-center justify-between flex-shrink-0">
        <p className="text-white/30 text-[10px] uppercase tracking-wider">Detalle de Radio</p>
        <button
          onClick={onClose}
          className="text-white/30 hover:text-white text-xs transition-colors leading-none"
        >
          ✕
        </button>
      </div>

      <div className="overflow-y-auto flex-1">

        {/* Score badge */}
        <div className="px-4 pt-4 pb-3 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div
              className="w-14 h-14 rounded-xl flex items-center justify-center text-white font-bold text-xl flex-shrink-0 shadow-lg"
              style={{ backgroundColor: scoreColor(score) }}
            >
              {score.toFixed(0)}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-white font-semibold">
                  {isInterior ? `Q${selected.alpha_quintil}` : scoreLabel(score, isGBA)}
                </span>
                <span
                  className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                    isInterior
                      ? "bg-slate-500/20 text-slate-300"
                      : isGBA
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-emerald-500/20 text-emerald-300"
                  }`}
                >
                  {isInterior
                    ? `${(selected as unknown as InteriorRadio).nombre_ciudad} · proxy`
                    : isGBA ? "GBA parcial" : "CABA completo"}
                </span>
              </div>
              <p className="text-white/40 text-[11px] font-mono truncate">
                Q{selected.alpha_quintil} · {selected.link}
              </p>
              {isGBA && (selected as GBARadio).nombre_partido && (
                <p className="text-amber-400/70 text-xs mt-0.5">
                  {(selected as GBARadio).nombre_partido}
                </p>
              )}
              {isInterior && (selected as unknown as InteriorRadio).departamento && (
                <p className="text-slate-400/70 text-xs mt-0.5">
                  Depto. {(selected as unknown as InteriorRadio).departamento}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Interior city notice */}
        {isInterior && (
          <div className="px-4 py-3 border-b border-white/10">
            <div className="bg-slate-500/10 border border-slate-500/20 rounded-lg px-3 py-2.5">
              <p className="text-slate-400 text-[10px] font-semibold uppercase tracking-wider mb-1">
                Score provisional
              </p>
              <p className="text-slate-400/70 text-[10px] leading-relaxed">
                Proxy geométrico por área de radio censal. El pipeline con POIs (transporte, comercio, servicios) aún no corrió para esta ciudad.
              </p>
            </div>
          </div>
        )}

        {/* CABA driver bars */}
        {!isGBA && !isInterior && (
          <div className="px-4 py-3 border-b border-white/10">
            <p className="text-white/30 text-[10px] uppercase tracking-wider mb-3">
              Drivers del Score
            </p>
            <div className="space-y-2.5">
              {CABA_DRIVERS.map((d) => {
                const cabaRadio = selected as CABARadio;
                return (
                  <div key={d.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className={`text-[10px] ${d.hasData ? "text-white/60" : "text-white/25"}`}
                      >
                        {d.label}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-white/25 text-[10px] tabular-nums">
                          {d.weight}%
                        </span>
                        <span
                          className={`text-[10px] font-mono w-24 text-right ${
                            d.hasData ? "text-white/55" : "text-white/20"
                          }`}
                        >
                          {d.getValue(cabaRadio)}
                        </span>
                      </div>
                    </div>
                    <div className="h-1 bg-white/[0.06] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${(d.weight / MAX_WEIGHT) * 100}%`,
                          backgroundColor: d.hasData ? d.color : "rgba(255,255,255,0.1)",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Metrics grid */}
        <div className="px-4 py-3">
          <p className="text-white/30 text-[10px] uppercase tracking-wider mb-2">Métricas</p>
          <div className="grid grid-cols-2 gap-1.5">

            {/* CABA */}
            {!isGBA && !isInterior && (() => {
              const r = selected as CABARadio;
              return (
                <>
                  <Stat label="Quintil"   value={`Q${r.alpha_quintil}`} />
                  <Stat label="Pob/km²"   value={Number(r.densidad_pob).toLocaleString()} />
                  <Stat label="Subte"     value={`${Math.round(Number(r.dist_subte_m))} m`} />
                  <Stat label="POIs/km²"  value={Number(r.poi_total_density).toFixed(0)} />
                  {r.pct_sin_nbi != null && (
                    <Stat label="% sin NBI" value={`${(Number(r.pct_sin_nbi) * 100).toFixed(1)}%`} />
                  )}
                  <Stat label="Diversidad" value={Number(r.div_entropy_ex_transporte).toFixed(3)} />
                  <div className="col-span-2 bg-white/[0.04] rounded-lg px-2.5 py-2 border border-white/[0.06]">
                    <p className="text-white/30 text-[10px]">Subte más cercano</p>
                    <p className="text-white/75 text-xs mt-0.5 truncate">{r.nearest_subte}</p>
                  </div>
                </>
              );
            })()}

            {/* GBA */}
            {isGBA && (() => {
              const r = selected as GBARadio;
              return (
                <>
                  <Stat label="Quintil"  value={`Q${r.alpha_quintil}`} />
                  <Stat label="Pob/km²"  value={Number(r.densidad_pob).toLocaleString()} />
                  <Stat label="Área"     value={`${Number(r.area_km2).toFixed(2)} km²`} />
                  {r.dist_tren_m != null && (
                    <Stat label="Dist. tren" value={`${Math.round(Number(r.dist_tren_m))} m`} />
                  )}
                  {r.poi_total_density != null && (
                    <Stat label="POIs/km²" value={Number(r.poi_total_density).toFixed(1)} />
                  )}
                </>
              );
            })()}

            {/* Interior */}
            {isInterior && (() => {
              const r = selected as unknown as InteriorRadio;
              return (
                <>
                  <Stat label="Quintil"    value={`Q${r.alpha_quintil}`} />
                  <Stat label="Score"      value={r.alpha_score.toFixed(1)} />
                  {r.departamento && <Stat label="Depto." value={r.departamento} />}
                  <Stat label="Versión"    value={r.score_version} />
                </>
              );
            })()}

          </div>
        </div>

      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white/[0.04] rounded-lg px-2.5 py-2 border border-white/[0.06]">
      <p className="text-white/30 text-[10px]">{label}</p>
      <p className="text-white/80 font-medium text-sm mt-0.5">{value}</p>
    </div>
  );
}
