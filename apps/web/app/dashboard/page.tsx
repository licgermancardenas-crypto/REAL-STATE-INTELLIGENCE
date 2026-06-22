import { CitySelector } from "@/components/dashboard/CitySelector";
import { KpiGrid } from "@/components/dashboard/KpiGrid";
import { AlphaMap } from "@/components/map/AlphaMap";
import { TopZonesTable } from "@/components/dashboard/TopZonesTable";

export default function DashboardPage() {
  return (
    <div className="flex h-screen bg-gray-950">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-800 flex flex-col p-4 gap-6">
        <div>
          <h1 className="text-lg font-bold text-white tracking-tight">RSI</h1>
          <p className="text-xs text-gray-500">Real State Intelligence</p>
        </div>
        <CitySelector />
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="border-b border-gray-800 px-6 py-4">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-widest">
            Executive Dashboard
          </h2>
        </header>

        <div className="flex-1 flex overflow-hidden">
          {/* Map panel */}
          <div className="flex-1 relative">
            <AlphaMap />
          </div>

          {/* Right panel */}
          <div className="w-80 border-l border-gray-800 flex flex-col overflow-y-auto p-4 gap-6">
            <KpiGrid />
            <TopZonesTable />
          </div>
        </div>
      </main>
    </div>
  );
}
