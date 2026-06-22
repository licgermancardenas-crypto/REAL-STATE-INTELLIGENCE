CREATE TABLE IF NOT EXISTS radios_censales (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    city_id         VARCHAR(20) REFERENCES cities(id),
    radio_id        VARCHAR(20) NOT NULL,         -- código INDEC
    name            TEXT,
    geometry        GEOMETRY(MULTIPOLYGON, 4326),
    population      INT,
    households      INT,
    nse_index       FLOAT,                        -- índice nivel socioeconómico 0-1
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(city_id, radio_id)
);

CREATE INDEX idx_radios_city ON radios_censales(city_id);
CREATE INDEX idx_radios_geom ON radios_censales USING GIST(geometry);
