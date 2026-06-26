"""
Tabla Gap de Valor — barrios CABA ordenados por ratio precio/alpha.

ratio_gap = precio_normalizado_CABA / alpha_score_mediano
  - precio_normalizado: usd_m2_mediano escalado 0-100 dentro de la muestra
  - ratio bajo  → barrio barato en precio PERO con buenos fundamentals
                   (el mercado no llegó o no valora lo que el Alpha mide)
  - ratio alto  → barrio caro relativo a sus fundamentals objetivos
                   (prima de marca, percepción, historia del barrio)

ADVERTENCIA METODOLÓGICA (incorporada en el output):
  La correlación entre alpha_score y precio mediano es r = +0.025, R² = 0.001
  (n=26 barrios, p=0.902 — no significativa). El Alpha Score NO predice precio.
  Esta tabla es DESCRIPTIVA: muestra la divergencia entre ambas dimensiones,
  no implica causalidad ni capacidad predictiva.

Uso:
  python scripts/tabla_gap_valor.py
  python scripts/tabla_gap_valor.py --min-listings 8
"""
import argparse
import warnings
from pathlib import Path

import pandas as pd
from scipy.stats import percentileofscore

warnings.filterwarnings("ignore")

ROOT      = Path(__file__).parent.parent
DATA_PROC = ROOT / "data/processed"
LOTES     = [DATA_PROC / "caba_wide_lote1_alpha.csv",
             DATA_PROC / "caba_wide_lote2_alpha.csv"]

# Valores de referencia del diagnóstico OLS ya corrido
OLS_R        = 0.025
OLS_R2       = 0.001
OLS_P        = 0.902
N_BARRIOS_OLS = 26

def load_barrios(min_n: int) -> pd.DataFrame:
    frames = [pd.read_csv(p, encoding="utf-8") for p in LOTES if p.exists()]
    raw = pd.concat(frames, ignore_index=True).drop_duplicates(subset="id_listing")
    raw["alpha_score"] = pd.to_numeric(raw["alpha_score"], errors="coerce")
    raw["usd_m2"]      = pd.to_numeric(raw["usd_m2"],      errors="coerce")
    sub = raw[raw["barrio"].notna() & raw["usd_m2"].notna() & raw["alpha_score"].notna()]

    barrio = (
        sub.groupby("barrio")
        .agg(
            n          =("usd_m2",     "count"),
            usd_m2_med =("usd_m2",     "median"),
            usd_m2_avg =("usd_m2",     "mean"),
            usd_m2_p25 =("usd_m2",     lambda x: x.quantile(0.25)),
            usd_m2_p75 =("usd_m2",     lambda x: x.quantile(0.75)),
            alpha_med  =("alpha_score", "median"),
        )
        .reset_index()
        .rename(columns={"barrio": "barrio"})
    )
    return barrio[barrio["n"] >= min_n].copy().reset_index(drop=True)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    # Normalizar precio 0-100 dentro de la muestra
    mn, mx = df["usd_m2_med"].min(), df["usd_m2_med"].max()
    df["precio_norm"] = (df["usd_m2_med"] - mn) / (mx - mn) * 100

    # Ratio gap = precio_norm / alpha (menor = más fundamentals por peso)
    df["ratio_gap"] = df["precio_norm"] / df["alpha_med"]

    # Percentiles dentro de la muestra (0-100)
    usd_vals   = df["usd_m2_med"].tolist()
    alpha_vals = df["alpha_med"].tolist()
    ratio_vals = df["ratio_gap"].tolist()

    df["pct_precio"] = df["usd_m2_med"].apply(
        lambda v: round(percentileofscore(usd_vals, v, kind="rank"))
    )
    df["pct_alpha"] = df["alpha_med"].apply(
        lambda v: round(percentileofscore(alpha_vals, v, kind="rank"))
    )
    df["pct_ratio"] = df["ratio_gap"].apply(
        lambda v: round(percentileofscore(ratio_vals, v, kind="rank"))
    )

    return df.sort_values("ratio_gap").reset_index(drop=True)


def print_table(df: pd.DataFrame, min_n: int):
    W = 82
    print(f"\n{'═'*W}")
    print("TABLA GAP DE VALOR — CABA barrios × Alpha Score")
    print(f"{'─'*W}")
    print("  ratio_gap = precio_norm_CABA / alpha_score_mediano")
    print("  Orden ascendente: ratio bajo = más fundamentals por peso (valor objetivo)")
    print("                    ratio alto = más caro relativo a fundamentals (marca)")
    print(f"{'─'*W}")
    print(f"  ⚠  ADVERTENCIA METODOLÓGICA:")
    print(f"     La correlación alpha ↔ precio es r = {OLS_R:+.3f}, R² = {OLS_R2:.3f}"
          f"  (p = {OLS_P:.3f}, n = {N_BARRIOS_OLS} barrios)")
    print(f"     El Alpha Score NO predice precio. Esta tabla muestra DIVERGENCIA")
    print(f"     entre ambas dimensiones — no implica causalidad ni poder predictivo.")
    print(f"{'═'*W}")

    hdr = (f"  {'#':>2}  {'Barrio':<22}  {'n':>4}  "
           f"{'Alpha':>6}  {'Pct-α':>5}  "
           f"{'USD/m²':>8}  {'Pct-$':>5}  "
           f"{'Precio':>6}  {'Ratio':>6}  Señal")
    sep = (f"  {'─'*2}  {'─'*22}  {'─'*4}  "
           f"{'─'*6}  {'─'*5}  "
           f"{'─'*8}  {'─'*5}  "
           f"{'─'*6}  {'─'*6}  {'─'*18}")
    print(f"\n  Col.  Precio = precio normalizado 0-100 dentro de CABA")
    print(f"  Col.  Ratio  = precio_norm / alpha  (ordenador principal)")
    print()
    print(hdr)
    print(sep)

    for i, row in df.iterrows():
        # Clasificación de ratio
        pct_r = row["pct_ratio"]
        if   pct_r <= 20:  senal = "▼▼ valor alto"
        elif pct_r <= 40:  senal = "▼  valor"
        elif pct_r <= 60:  senal = "── justo"
        elif pct_r <= 80:  senal = "▲  premium"
        else:              senal = "▲▲ premium alto"

        # Confiabilidad
        conf = "" if row["n"] >= min_n else " ⚠️"

        print(
            f"  {i+1:>2}  {str(row['barrio']):<22}  {int(row['n']):>4}  "
            f"{row['alpha_med']:>6.1f}  {int(row['pct_alpha']):>4}%  "
            f"${row['usd_m2_med']:>7,.0f}  {int(row['pct_precio']):>4}%  "
            f"{row['precio_norm']:>6.1f}  {row['ratio_gap']:>6.3f}  "
            f"{senal}{conf}"
        )

    print(f"\n{'─'*W}")
    print("  RESUMEN:")

    valor = df[df["pct_ratio"] <= 33].copy()
    premi = df[df["pct_ratio"] >= 67].copy()

    if not valor.empty:
        print(f"\n  ▼ VALOR OBJETIVO (ratio bajo — fundamentals altos, precio contenido):")
        for _, r in valor.iterrows():
            print(f"    {r['barrio']:<22}  alpha={r['alpha_med']:.1f} (p{int(r['pct_alpha'])})"
                  f"  ${r['usd_m2_med']:,.0f}/m² (p{int(r['pct_precio'])}) "
                  f"  ratio={r['ratio_gap']:.3f}")

    if not premi.empty:
        print(f"\n  ▲ PREMIUM DE MARCA (ratio alto — precio alto, fundamentals relativos):")
        for _, r in premi.iterrows():
            print(f"    {r['barrio']:<22}  alpha={r['alpha_med']:.1f} (p{int(r['pct_alpha'])})"
                  f"  ${r['usd_m2_med']:,.0f}/m² (p{int(r['pct_precio'])}) "
                  f"  ratio={r['ratio_gap']:.3f}")

    print(f"\n{'═'*W}")


def save(df: pd.DataFrame):
    out = DATA_PROC / "barrio_gap_valor.csv"
    cols = ["barrio", "n", "alpha_med", "pct_alpha",
            "usd_m2_med", "usd_m2_p25", "usd_m2_p75",
            "pct_precio", "precio_norm", "ratio_gap", "pct_ratio"]
    df[cols].to_csv(out, index=False, encoding="utf-8")
    print(f"  Guardado: {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-listings", type=int, default=6)
    args = parser.parse_args()

    df = load_barrios(args.min_listings)
    df = enrich(df)
    print_table(df, min_n=args.min_listings)
    save(df)


if __name__ == "__main__":
    main()
