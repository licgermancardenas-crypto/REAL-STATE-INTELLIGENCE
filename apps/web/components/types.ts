export interface CABARadio {
  link: string;
  alpha_score: number;
  alpha_quintil: number;
  score_version: string;
  tot_pob: number;
  densidad_pob: number;
  poi_total_count: number;
  poi_total_density: number;
  div_entropy_ex_transporte: number;
  dist_subte_m: number;
  nearest_subte: string;
  pct_sin_nbi?: number;
  score_tipo?: never;
}

export interface GBARadio {
  link: string;
  depto_code: string;
  nombre_partido: string;
  alpha_score: number;
  alpha_quintil: number;
  tot_pob: number;
  densidad_pob: number;
  area_km2: number;
  poi_total_density?: number;
  dist_tren_m?: number;
  score_tipo: "parcial" | "completo";
}

export interface InteriorRadio {
  link: string;
  ciudad: string;
  nombre_ciudad: string;
  provincia?: string;
  departamento?: string;
  alpha_score: number;
  alpha_quintil: number;
  score_version: string;
  score_tipo: "geometrico" | "parcial" | "completo";
  tot_pob?: number;
  densidad_pob?: number;
}

export type CityId = "caba" | "gba" | "rosario" | "cordoba" | "mendoza";

export type SelectedRadio =
  | (CABARadio & { _ciudad: "caba" })
  | (GBARadio & { _ciudad: "gba" })
  | (InteriorRadio & { _ciudad: Exclude<CityId, "caba" | "gba"> });

export interface CityConfig {
  id: CityId;
  name: string;
  short: string;
  center: [number, number];
  zoom: number;
  geojson: string;
  scoreType: "completo" | "parcial" | "geometrico";
  variables: number;
}

export interface Stats {
  count: number;
  mean: number;
  median: number;
  max: number;
  premiumCount: number;
  top: CABARadio[];
}

export const CITIES: CityConfig[] = [
  {
    id: "caba",
    name: "Ciudad Autónoma de Buenos Aires",
    short: "CABA",
    center: [-58.44, -34.62],
    zoom: 11.5,
    geojson: "/caba_alpha_scores.geojson",
    scoreType: "completo",
    variables: 8,
  },
  {
    id: "gba",
    name: "Gran Buenos Aires",
    short: "Conurbano",
    center: [-58.65, -34.70],
    zoom: 9.5,
    geojson: "/gba_alpha_scores.geojson",
    scoreType: "parcial",
    variables: 3,
  },
  {
    id: "rosario",
    name: "Rosario",
    short: "Rosario",
    center: [-60.65, -32.945],
    zoom: 11.5,
    geojson: "/rosario_alpha_scores.geojson",
    scoreType: "geometrico",
    variables: 1,
  },
  {
    id: "cordoba",
    name: "Córdoba",
    short: "Córdoba",
    center: [-64.185, -31.415],
    zoom: 11.5,
    geojson: "/cordoba_alpha_scores.geojson",
    scoreType: "geometrico",
    variables: 1,
  },
  {
    id: "mendoza",
    name: "Gran Mendoza",
    short: "Mendoza",
    center: [-68.865, -32.89],
    zoom: 11.5,
    geojson: "/mendoza_alpha_scores.geojson",
    scoreType: "geometrico",
    variables: 1,
  },
];

export const COLOR_STOPS = [
  [1,    "#0f172a"],
  [20,   "#1e3a5f"],
  [27,   "#1d4ed8"],
  [35,   "#059669"],
  [45,   "#d97706"],
  [97.7, "#dc2626"],
] as const;

export function scoreColor(score: number): string {
  for (let i = COLOR_STOPS.length - 1; i >= 0; i--)
    if (score >= COLOR_STOPS[i][0]) return COLOR_STOPS[i][1];
  return COLOR_STOPS[0][1];
}

export function scoreLabel(score: number, gba = false): string {
  if (gba) {
    if (score >= 70) return "Alta densidad";
    if (score >= 50) return "Media-alta";
    if (score >= 30) return "Media";
    return "Baja densidad";
  }
  if (score >= 45) return "Premium";
  if (score >= 35) return "Alto";
  if (score >= 27) return "Medio";
  if (score >= 20) return "Bajo";
  return "Mínimo";
}
