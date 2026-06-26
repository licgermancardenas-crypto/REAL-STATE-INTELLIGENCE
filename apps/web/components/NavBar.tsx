"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/",    label: "Alpha Score",  sub: "AMBA · Radio censal" },
  { href: "/gap", label: "Gap de Valor", sub: "CABA · Barrios" },
];

export default function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="h-10 flex-shrink-0 flex items-center px-4 border-b border-white/10 bg-[#080c14] gap-6">
      {/* Brand */}
      <div className="flex items-center gap-2 mr-4">
        <span className="text-emerald-400 text-[11px] font-bold tracking-[0.25em] uppercase">RSI</span>
        <span className="text-white/15 text-xs">·</span>
        <span className="text-white/25 text-[10px] tracking-widest uppercase">Real State Intelligence</span>
      </div>

      {/* Divider */}
      <div className="h-4 w-px bg-white/10 flex-shrink-0" />

      {/* Nav links */}
      <div className="flex items-center gap-1">
        {LINKS.map(({ href, label, sub }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-[11px] font-medium transition-colors ${
                active
                  ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/25"
                  : "text-white/35 hover:text-white/70 hover:bg-white/5"
              }`}
            >
              {label}
              <span className={`text-[9px] font-normal ${active ? "text-emerald-400/60" : "text-white/20"}`}>
                {sub}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
