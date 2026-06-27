"use client";

import { useCallback } from "react";

interface Props {
  min: number;
  max: number;
  value: [number, number];
  step?: number;
  onChange: (range: [number, number]) => void;
}

export default function RangeSlider({ min, max, value, step = 0.01, onChange }: Props) {
  const [lo, hi] = value;
  const pct = (v: number) => ((v - min) / (max - min)) * 100;

  const onLo = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = Math.min(Number(e.target.value), hi - step);
      onChange([v, hi]);
    },
    [hi, step, onChange],
  );

  const onHi = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = Math.max(Number(e.target.value), lo + step);
      onChange([lo, v]);
    },
    [lo, step, onChange],
  );

  return (
    <div className="px-1 pt-3 pb-1">
      <div className="relative h-4">
        {/* Track */}
        <div className="absolute top-1/2 -translate-y-1/2 w-full h-1 rounded-full bg-white/10" />
        {/* Active range */}
        <div
          className="absolute top-1/2 -translate-y-1/2 h-1 rounded-full bg-emerald-500/60"
          style={{ left: `${pct(lo)}%`, right: `${100 - pct(hi)}%` }}
        />
        {/* Lo thumb */}
        <input
          type="range" min={min} max={max} step={step} value={lo}
          onChange={onLo}
          className="absolute w-full h-full opacity-0 cursor-pointer"
          style={{ zIndex: lo > max - (max - min) * 0.1 ? 5 : 3 }}
        />
        {/* Hi thumb */}
        <input
          type="range" min={min} max={max} step={step} value={hi}
          onChange={onHi}
          className="absolute w-full h-full opacity-0 cursor-pointer"
          style={{ zIndex: 4 }}
        />
        {/* Thumb visuals */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-emerald-400 border-2 border-white/80 shadow pointer-events-none"
          style={{ left: `${pct(lo)}%`, zIndex: 6 }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-emerald-400 border-2 border-white/80 shadow pointer-events-none"
          style={{ left: `${pct(hi)}%`, zIndex: 6 }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-white/35 mt-1.5">
        <span>{lo.toFixed(2)}</span>
        <span>{hi.toFixed(2)}</span>
      </div>
    </div>
  );
}
