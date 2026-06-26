import { CABARadio, scoreColor } from "./types";

function topDriver(r: CABARadio): string {
  const subte = Number(r.dist_subte_m);
  const pois  = Number(r.poi_total_density);
  const div   = Number(r.div_entropy_ex_transporte);

  const subteScore = subte < 300 ? 3 : subte < 600 ? 2 : subte < 1100 ? 1 : 0;
  const poisScore  = pois > 800  ? 3 : pois > 400  ? 2 : pois > 150   ? 1 : 0;
  const divScore   = div > 1.5   ? 3 : div > 1.0   ? 2 : div > 0.6    ? 1 : 0;

  const max = Math.max(subteScore, poisScore, divScore);
  if (max === 0) return "Multifactor";
  if (subteScore === max) return `Subte · ${Math.round(subte)}m`;
  if (poisScore === max)  return `${Math.round(pois)} POIs/km²`;
  return `Div. ${div.toFixed(2)}`;
}

export default function TopZonesTable({
  radios,
  selectedLink,
  onSelect,
}: {
  radios: CABARadio[];
  selectedLink: string | null;
  onSelect: (r: CABARadio) => void;
}) {
  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-4 py-2.5 flex-shrink-0 border-b border-white/10">
        <p className="text-white/30 text-[10px] uppercase tracking-wider">
          Top 10 Radios · CABA
        </p>
      </div>
      <div className="overflow-y-auto flex-1">
        {radios.slice(0, 10).map((r, i) => {
          const isSelected = r.link === selectedLink;
          return (
            <button
              key={r.link}
              onClick={() => onSelect(r)}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-left border-b border-white/[0.05] transition-colors ${
                isSelected
                  ? "bg-white/[0.08] border-l-2 border-l-emerald-500"
                  : "hover:bg-white/[0.04]"
              }`}
            >
              <span className="text-white/25 text-[11px] w-4 text-right flex-shrink-0 tabular-nums">
                {i + 1}
              </span>
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                style={{ backgroundColor: scoreColor(Number(r.alpha_score)) }}
              >
                {Number(r.alpha_score).toFixed(0)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white/70 text-xs font-mono truncate">{r.link}</p>
                <p className="text-white/30 text-[10px] truncate">{topDriver(r)}</p>
              </div>
              <span className="text-white/25 text-[10px] flex-shrink-0">
                Q{r.alpha_quintil}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
