"""
Premium de Marca — residual de regresión usd_m2 ~ alpha_score a nivel barrio.

Protocolo de salida (en orden):
  1. Diagnóstico OLS: slope (vs lote1 baseline −18.77), R², p-value
  2. Si p > 0.05 o slope ≥ 0 → AVISO explícito y salida (sin ranking)
  3. Si p ≤ 0.05 y slope < 0 → ranking completo con marcas de confiabilidad
     * barrios con n < MIN_CONF marcados ⚠️ (muestra pequeña)

Uso:
  python scripts/analisis_premium_marca.py
  python scripts/analisis_premium_marca.py --min-listings 8 --min-confiable 10
"""
import argparse
import sys
import warnings
from pathlib import Path

import pandas as pd
from scipy import stats as scipy_stats

warnings.filterwarnings("ignore")

ROOT      = Path(__file__).parent.parent
DATA_PROC = ROOT / "data/processed"

LOTES = [
    DATA_PROC / "caba_wide_lote1_alpha.csv",
    DATA_PROC / "caba_wide_lote2_alpha.csv",
]

SLOPE_LOTE1 = -18.77   # baseline de referencia para comparar dirección

# ── Load + merge ──────────────────────────────────────────────────────────────

def load_data(min_listings: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    for p in LOTES:
        if p.exists():
            df = pd.read_csv(p, encoding="utf-8")
            frames.append(df)
            print(f"  Cargado: {p.name}  ({len(df):,} filas)")
        else:
            print(f"  No encontrado (skip): {p.name}")

    if not frames:
        raise FileNotFoundError("No hay ningún lote disponible.")

    raw = pd.concat(frames, ignore_index=True)
    before = len(raw)
    raw    = raw.drop_duplicates(subset="id_listing", keep="first")
    print(f"  Deduplicados: {before:,} → {len(raw):,} listings únicos\n")

    raw["alpha_score"] = pd.to_numeric(raw["alpha_score"], errors="coerce")
    raw["usd_m2"]      = pd.to_numeric(raw["usd_m2"],      errors="coerce")

    sub = raw[
        raw["barrio"].notna() &
        raw["usd_m2"].notna() &
        raw["alpha_score"].notna()
    ].copy()

    barrio = (
        sub.groupby("barrio")
        .agg(
            n          =("usd_m2",     "count"),
            med_usd_m2 =("usd_m2",     "median"),
            avg_usd_m2 =("usd_m2",     "mean"),
            p25        =("usd_m2",     lambda x: x.quantile(0.25)),
            p75        =("usd_m2",     lambda x: x.quantile(0.75)),
            med_alpha  =("alpha_score", "median"),
            avg_alpha  =("alpha_score", "mean"),
        )
        .reset_index()
    )
    filtered = barrio[barrio["n"] >= min_listings].copy().reset_index(drop=True)
    print(f"  Barrios con ≥{min_listings} listings: {len(filtered)} "
          f"(de {len(barrio)} totales)")
    return sub, filtered

# ── OLS ───────────────────────────────────────────────────────────────────────

def run_ols(barrio: pd.DataFrame):
    x = barrio["med_alpha"].values
    y = barrio["med_usd_m2"].values
    slope, intercept, r, p, se = scipy_stats.linregress(x, y)
    r2 = r ** 2
    r_s, p_s = scipy_stats.spearmanr(x, y)
    return slope, intercept, r, r2, p, se, r_s, p_s

# ── Diagnostics block (always printed first) ──────────────────────────────────

def print_diagnostics(slope, intercept, r, r2, p, se, r_s, p_s,
                      n_barrios, slope_ref=SLOPE_LOTE1) -> bool:
    W = 72
    print(f"\n{'═'*W}")
    print(f"DIAGNÓSTICO OLS  —  med_usd_m2 ~ med_alpha_score  (n={n_barrios} barrios)")
    print(f"{'═'*W}")

    # Slope comparison
    cambio = slope - slope_ref
    if   slope > 0:           direccion = "POSITIVO  ← cambio de signo respecto a lote1"
    elif abs(slope) < abs(slope_ref) * 0.5: direccion = "negativo moderado (se acercó a 0)"
    else:                     direccion = "negativo  (misma dirección que lote1)"

    print(f"\n  Slope actual    = {slope:+.2f} USD/m² por punto de alpha  [{direccion}]")
    print(f"  Slope lote1     = {slope_ref:+.2f} USD/m² por punto de alpha  (referencia)")
    print(f"  Δ slope         = {cambio:+.2f}")
    print(f"  Intercept       = {intercept:,.0f} USD/m²")
    print(f"  SE (slope)      = {se:.2f}")
    print(f"\n  Pearson  r      = {r:+.3f}   R² = {r2:.3f}")
    print(f"  Spearman rho    = {r_s:+.3f}   p  = {p_s:.4f}")
    print(f"  p-value (OLS)   = {p:.4f}")

    # R² interpretation
    print(f"\n  R² = {r2:.3f} → el alpha_score explica el {r2*100:.1f}% de la varianza "
          f"de precio entre barrios.")
    if r2 < 0.10:
        r2_label = "MUY BAJO — residuales individuales tienen ruido muy alto."
    elif r2 < 0.20:
        r2_label = "BAJO — residuales con ruido considerable."
    elif r2 < 0.40:
        r2_label = "MODERADO — señal útil pero imprecisa."
    else:
        r2_label = "ALTO — residuales razonablemente confiables."
    print(f"  Interpretación  : {r2_label}")

    # Gate conditions
    print(f"\n{'─'*W}")
    proceed = True

    if p > 0.05:
        print(f"  ⛔  p = {p:.4f} > 0.05 — la regresión NO ES SIGNIFICATIVA.")
        print(f"      El alpha_score no tiene poder predictivo lineal claro sobre precio.")
        print(f"      Conclusión: no se puede construir un ranking de 'caro/barato' con")
        print(f"      fundamento estadístico en este dataset. Esto ES un resultado legítimo.")
        proceed = False

    if slope >= 0:
        print(f"  ⛔  slope = {slope:+.2f} ≥ 0 — la relación cambió de signo.")
        print(f"      Con slope positivo, la interpretación del residual cambia completa-")
        print(f"      mente. Hay que revisar la composición del dataset antes de continuar.")
        proceed = False

    if not proceed:
        print(f"{'─'*W}")
        print(f"  Ranking de residuales OMITIDO por las condiciones anteriores.")
        print(f"{'═'*W}")
    else:
        print(f"  ✓  Condiciones cumplidas: slope < 0, p ≤ 0.05.")
        if r2 < 0.20:
            print(f"  ⚠️  R² bajo ({r2:.3f}): los residuales deben leerse con cautela.")
            print(f"      Un residual 'grande' en un barrio pequeño puede ser ruido puro.")
        print(f"{'─'*W}")

    return proceed

# ── Ranking ───────────────────────────────────────────────────────────────────

def print_ranking(barrio: pd.DataFrame, slope: float, intercept: float,
                  r2: float, min_conf: int):
    barrio = barrio.copy()
    barrio["pred_usd_m2"] = intercept + slope * barrio["med_alpha"]
    barrio["residual"]    = barrio["med_usd_m2"] - barrio["pred_usd_m2"]
    res_std               = barrio["residual"].std()
    barrio["residual_sd"] = barrio["residual"] / res_std

    ranked = barrio.sort_values("residual", ascending=False).reset_index(drop=True)

    W = 78
    r2_caveat = f"  [R²={r2:.2f} — " + (
        "ruido alto, leer con cautela]" if r2 < 0.20 else
        "señal moderada]"               if r2 < 0.40 else
        "señal robusta]"
    )
    print(f"\n{'═'*W}")
    print(f"RANKING PREMIUM DE MARCA  {r2_caveat}")
    print(f"{'═'*W}")
    print(f"  Residual > 0 → precio real MAYOR que el alpha predice → premium de marca")
    print(f"  Residual < 0 → precio real MENOR que el alpha predice → oportunidad objetiva")
    print(f"  ⚠️ = n < {min_conf} listings (estimación poco confiable)")
    print()
    print(f"  {'#':>2}  {'Barrio':<22}  {'n':>4}  {'Alpha':>6}  "
          f"{'Real':>9}  {'Pred':>9}  {'Res.':>8}  {'SD':>5}  Señal")
    print(f"  {'─'*2}  {'─'*22}  {'─'*4}  {'─'*6}  "
          f"{'─'*9}  {'─'*9}  {'─'*8}  {'─'*5}  {'─'*14}")

    for i, row in ranked.iterrows():
        sd   = row["residual_sd"]
        conf = "" if row["n"] >= min_conf else " ⚠️"

        if   sd >  1.5: senal = "CARO  ↑↑↑"
        elif sd >  0.7: senal = "caro   ↑"
        elif sd < -1.5: senal = "BARATO ↓↓↓"
        elif sd < -0.7: senal = "barato ↓"
        else:           senal = "justo ~"

        print(
            f"  {i+1:>2}  {str(row['barrio']):<22}  {int(row['n']):>4}  "
            f"{row['med_alpha']:>6.1f}  "
            f"${row['med_usd_m2']:>8,.0f}  "
            f"${row['pred_usd_m2']:>8,.0f}  "
            f"{row['residual']:>+8,.0f}  "
            f"{sd:>+5.2f}  "
            f"{senal}{conf}"
        )

    # Summary tables — only confiable barrios
    print(f"\n{'─'*W}")
    confiable = ranked[ranked["n"] >= min_conf]

    caros   = confiable[confiable["residual_sd"] >  0.5]
    baratos = confiable[confiable["residual_sd"] < -0.5]

    if not caros.empty:
        print(f"\n  ▲ CAROS (muestra confiable, n≥{min_conf}) — premium de marca/percepción:")
        for _, r in caros.iterrows():
            print(f"    {r['barrio']:<22}  alpha={r['med_alpha']:.1f}  "
                  f"real=${r['med_usd_m2']:,.0f}  pred=${r['pred_usd_m2']:,.0f}  "
                  f"+${r['residual']:,.0f}/m² ({r['residual_sd']:+.1f}σ)  n={int(r['n'])}")

    if not baratos.empty:
        print(f"\n  ▼ BARATOS (muestra confiable, n≥{min_conf}) — oportunidad objetiva:")
        for _, r in baratos[::-1].iterrows():
            print(f"    {r['barrio']:<22}  alpha={r['med_alpha']:.1f}  "
                  f"real=${r['med_usd_m2']:,.0f}  pred=${r['pred_usd_m2']:,.0f}  "
                  f"${r['residual']:,.0f}/m² ({r['residual_sd']:+.1f}σ)  n={int(r['n'])}")

    # Save
    out = DATA_PROC / "barrio_premium_marca.csv"
    ranked.to_csv(out, index=False, encoding="utf-8")
    print(f"\n  Guardado: {out}")
    print(f"{'═'*W}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-listings",  type=int, default=6,
                        help="Mínimo de listings para incluir un barrio en la regresión")
    parser.add_argument("--min-confiable", type=int, default=8,
                        help="Mínimo para considerar el residual de un barrio confiable")
    args = parser.parse_args()

    print("Cargando datos…")
    sub, barrio = load_data(args.min_listings)

    slope, intercept, r, r2, p, se, r_s, p_s = run_ols(barrio)

    proceed = print_diagnostics(slope, intercept, r, r2, p, se, r_s, p_s,
                                 n_barrios=len(barrio))
    if not proceed:
        sys.exit(0)

    print_ranking(barrio, slope, intercept, r2, min_conf=args.min_confiable)

if __name__ == "__main__":
    main()
