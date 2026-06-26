import ValueGapMapLoader from "@/components/ValueGapMapLoader";

export const metadata = {
  title: "Gap de Valor · RSI",
  description: "Análisis descriptivo de divergencia entre fundamentals objetivos y precio de mercado en CABA",
};

export default function GapPage() {
  return (
    <main className="w-full h-full flex overflow-hidden bg-[#0f172a]">
      <ValueGapMapLoader />
    </main>
  );
}
