CREATE TABLE IF NOT EXISTS listings (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    city_id         VARCHAR(20) REFERENCES cities(id),
    radio_id        UUID REFERENCES radios_censales(id),
    address         TEXT,
    location        GEOGRAPHY(POINT, 4326),
    property_type   VARCHAR(20),  -- depto, casa, ph, lote, local
    price_usd       FLOAT,
    surface_m2      FLOAT,
    price_usd_m2    FLOAT GENERATED ALWAYS AS (price_usd / NULLIF(surface_m2, 0)) STORED,
    rooms           INT,
    source          VARCHAR(20),  -- zonaprop, argenprop
    source_id       TEXT,
    scraped_at      DATE,
    alpha_score     FLOAT,
    UNIQUE(source, source_id)
);

CREATE INDEX idx_listings_city    ON listings(city_id);
CREATE INDEX idx_listings_location ON listings USING GIST(location);
CREATE INDEX idx_listings_scraped  ON listings(scraped_at DESC);
