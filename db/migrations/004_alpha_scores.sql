CREATE TABLE IF NOT EXISTS alpha_scores (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    radio_id        UUID REFERENCES radios_censales(id),
    city_id         VARCHAR(20) REFERENCES cities(id),
    score           FLOAT NOT NULL CHECK (score BETWEEN 0 AND 100),
    percentile      FLOAT,
    model_version   VARCHAR(20),
    -- Features snapshot
    poi_density_500m      FLOAT,
    street_connectivity   FLOAT,
    avg_price_usd_m2      FLOAT,
    price_delta_12m       FLOAT,
    transit_access_score  FLOAT,
    nse_index             FLOAT,
    new_permits_12m       INT,
    -- Prediction
    prediction_24m_pct    FLOAT,
    computed_at           TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alpha_city ON alpha_scores(city_id);
CREATE INDEX idx_alpha_score ON alpha_scores(score DESC);
