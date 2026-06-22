"""
Modelo Alpha Score.
Gradient Boosting sobre features espaciales → score 0-100 por radio censal.
Validación con Moran's I (PySAL/esda) para verificar autocorrelación espacial.
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

MODEL_DIR = Path(__file__).parent / "artifacts"
MODEL_DIR.mkdir(exist_ok=True)


class AlphaScoreModel:
    def __init__(self):
        self.model = GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            random_state=42,
        )
        self.scaler = MinMaxScaler(feature_range=(0, 100))
        self.feature_names: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        self.feature_names = list(X.columns)
        cv_scores = cross_val_score(self.model, X, y, cv=5, scoring="r2")
        logger.info(f"CV R² = {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
        self.model.fit(X, y)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raw = self.model.predict(X)
        scaled = self.scaler.fit_transform(raw.reshape(-1, 1)).flatten()
        return scaled

    def feature_importances(self) -> pd.Series:
        return pd.Series(
            self.model.feature_importances_,
            index=self.feature_names,
        ).sort_values(ascending=False)

    def validate_spatial(self, scores: np.ndarray, radios: gpd.GeoDataFrame) -> float:
        """Moran's I — verifica que el score tiene coherencia espacial."""
        w = libpysal.weights.Queen.from_dataframe(radios)
        w.transform = "r"
        mi = esda.Moran(scores, w)
        logger.info(f"Moran's I = {mi.I:.4f} (p={mi.p_sim:.4f})")
        return mi.I

    def save(self, city_id: str) -> None:
        joblib.dump({"model": self.model, "scaler": self.scaler, "features": self.feature_names},
                    MODEL_DIR / f"alpha_{city_id}.pkl")

    @classmethod
    def load(cls, city_id: str) -> "AlphaScoreModel":
        obj = cls()
        data = joblib.load(MODEL_DIR / f"alpha_{city_id}.pkl")
        obj.model = data["model"]
        obj.scaler = data["scaler"]
        obj.feature_names = data["features"]
        return obj
