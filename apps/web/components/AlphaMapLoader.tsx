"use client";

import dynamic from "next/dynamic";

const AlphaMap = dynamic(() => import("./AlphaMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-screen flex items-center justify-center bg-[#0f172a]">
      <p className="text-white/40 text-sm animate-pulse">Cargando mapa…</p>
    </div>
  ),
});

export default function AlphaMapLoader() {
  return <AlphaMap />;
}
