"""
Modelo de scoring ponderado por zona — Fase 3.
Dos modos:
  1. Weighted sum: pesos explícitos por feature (interpretable, auditable)
  2. GradientBoosting: entrenado sobre historial de precios (cuando hay datos suficientes)
"""
import numpy as np
import pandas as pd
import geopandas as gpd
import joblib
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import cross_val_score
import esda
import libpysal
from loguru import logger

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# Pesos para el modelo de suma ponderada (Fase 3 inicial)
# Cada peso refleja la contribución relativa al valor inmobiliario.
# Fuente: calibración manual basada en literatura PropTech + consenso mercado ARG.
DEFAULT_WEIGHTS = {
    "poi_density_500m": 0.20,
    "transit_stops_500m": 0.25,
    "street_connectivity": 0.15,
    "avg_price_usd_m2": 0.20,
    "densidad_pob": 0.10,
    "new_permits_12m": 0.10,
}


def weighted_score(features: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.Series:
    """
    Score 0-100 por suma ponderada de features normalizadas.
    Auditable: cada peso tiene fuente explícita.
    """
    w = weights or DEFAULT_WEIGHTS
    available = {k: v for k, v in w.items() if k in features.columns}
    if not available:
        raise ValueError(f"Ninguna feature en el DataFrame. Disponibles: {list(features.columns)}")

    total_weight = sum(available.values())
    score = sum(features[k] * v for k, v in available.items()) / total_weight
    return (score * 100).clip(0, 100).rename("alpha_score")


def moran_i(scores: pd.Series, radios: gpd.GeoDataFrame) -> float:
    """Validación espacial: Moran's I sobre el score calculado."""
    try:
        w = libpysal.weights.Queen.from_dataframe(radios.reset_index(drop=True))
        w.transform = "r"
        mi = esda.Moran(scores.values, w)
        logger.info(f"Moran's I = {mi.I:.4f} (p = {mi.p_sim:.4f})")
        return mi.I
    except Exception as e:
        logger.warning(f"Moran's I falló: {e}")
        return float("nan")


class AlphaScoreModel:
    """GBM entrenado — usar cuando haya historial de precios suficiente (Fase 3+)."""

    def __init__(self):
        self.model = GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            subsample=0.8, random_state=42,
        )
        self.scaler = MinMaxScaler(feature_range=(0, 100))
        self.feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        self.feature_names = list(X.columns)
        cv = cross_val_score(self.model, X, y, cv=5, scoring="r2")
        logger.info(f"CV R² = {cv.mean():.3f} ± {cv.std():.3f}")
        self.model.fit(X, y)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict(X)
        return self.scaler.fit_transform(raw.reshape(-1, 1)).flatten()

    def feature_importances(self) -> pd.Series:
        return pd.Series(self.model.feature_importances_, index=self.feature_names).sort_values(ascending=False)

    def save(self, nombre: str) -> None:
        joblib.dump(
            {"model": self.model, "scaler": self.scaler, "features": self.feature_names},
            ARTIFACTS_DIR / f"alpha_{nombre}.pkl",
        )

    @classmethod
    def load(cls, nombre: str) -> "AlphaScoreModel":
        obj = cls()
        data = joblib.load(ARTIFACTS_DIR / f"alpha_{nombre}.pkl")
        obj.model, obj.scaler, obj.feature_names = data["model"], data["scaler"], data["features"]
        return obj
