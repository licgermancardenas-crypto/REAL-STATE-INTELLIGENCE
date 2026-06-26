import { Stats } from "./types";

export default function KPICards({ stats }: { stats: Stats }) {
  return (
    <div className="p-4 border-b border-white/10 flex-shrink-0">
      <p className="text-white/30 text-[10px] uppercase tracking-wider mb-3">
        CABA · Score completo
      </p>
      <div className="grid grid-cols-2 gap-2">
        <KPICard label="Radios" value={stats.count.toLocaleString()} color="text-white" />
        <KPICard label="Mediana" value={stats.median.toFixed(1)} color="text-emerald-400" />
        <KPICard label="Premium Q5" value={stats.premiumCount.toString()} color="text-red-400" />
        <KPICard label="Score máx" value={stats.max.toFixed(1)} color="text-amber-400" />
      </div>
    </div>
  );
}

function KPICard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="bg-white/[0.04] rounded-lg p-3 border border-white/[0.06]">
      <p className="text-white/35 text-[10px] uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold mt-0.5 tabular-nums ${color}`}>{value}</p>
    </div>
  );
}
