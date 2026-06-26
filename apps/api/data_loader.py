"""
In-memory cache for GeoJSON data. Reads from apps/web/public/ (static files)
or from data/processed/scores/ (pipeline outputs). Falls back gracefully.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
PUBLIC = ROOT / "apps" / "web" / "public"
SCORES = ROOT / "data" / "processed" / "scores"


def _load_geojson(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def get_caba_geojson() -> dict[str, Any] | None:
    for p in [
        PUBLIC / "caba_alpha_scores.geojson",
        SCORES / "caba_radio_scores.geojson",
    ]:
        data = _load_geojson(p)
        if data:
            return data
    return None


@lru_cache(maxsize=None)
def get_gba_geojson() -> dict[str, Any] | None:
    for p in [
        PUBLIC / "gba_alpha_scores.geojson",
        SCORES / "gba_radio_scores.geojson",
    ]:
        data = _load_geojson(p)
        if data:
            return data
    return None


@lru_cache(maxsize=None)
def get_gap_geojson() -> dict[str, Any] | None:
    return _load_geojson(PUBLIC / "value_gap_caba.geojson")


def _compute_stats(features: list[dict], score_key: str = "alpha_score") -> dict:
    scores = sorted(
        f["properties"][score_key]
        for f in features
        if f.get("properties", {}).get(score_key) is not None
    )
    if not scores:
        return {}
    n = len(scores)
    mean = round(sum(scores) / n, 1)
    median = round(scores[n // 2], 1)
    p25 = round(scores[n // 4], 1)
    p75 = round(scores[3 * n // 4], 1)
    max_ = round(scores[-1], 1)
    premium = sum(
        1 for f in features
        if f.get("properties", {}).get("alpha_quintil") == 5
    )
    return {
        "count": n,
        "mean": mean,
        "median": median,
        "p25": p25,
        "p75": p75,
        "max": max_,
        "premium_count": premium,
    }


def caba_stats() -> dict:
    data = get_caba_geojson()
    if not data:
        return {}
    return _compute_stats(data["features"])


def gba_stats() -> dict:
    data = get_gba_geojson()
    if not data:
        return {}
    return _compute_stats(data["features"])


def invalidate_cache() -> None:
    get_caba_geojson.cache_clear()
    get_gba_geojson.cache_clear()
    get_gap_geojson.cache_clear()
