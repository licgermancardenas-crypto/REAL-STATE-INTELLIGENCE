"use client";

import dynamic from "next/dynamic";

const ValueGapMap = dynamic(() => import("./ValueGapMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-screen flex items-center justify-center bg-[#0f172a]">
      <p className="text-white/40 text-sm animate-pulse">Cargando mapa de gap…</p>
    </div>
  ),
});

export default function ValueGapMapLoader() {
  return <ValueGapMap />;
}
