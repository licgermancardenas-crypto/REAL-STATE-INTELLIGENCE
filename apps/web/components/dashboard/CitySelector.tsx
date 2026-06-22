"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

export function CitySelector() {
  const router = useRouter();
  const params = useSearchParams();
  const currentCity = params.get("city") ?? "caba";

  const { data: cities } = useQuery({
    queryKey: ["cities"],
    queryFn: () => api.get("/api/cities").then((r) => r.data),
  });

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Ciudad</span>
      {cities?.map((c: { id: string; name: string }) => (
        <button
          key={c.id}
          onClick={() => router.push(`/dashboard?city=${c.id}`)}
          className={`text-left px-3 py-2 rounded-lg text-sm transition-colors ${
            currentCity === c.id
              ? "bg-brand-700 text-white"
              : "text-gray-400 hover:bg-gray-800"
          }`}
        >
          {c.name}
        </button>
      ))}
    </div>
  );
}
