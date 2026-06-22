CREATE TABLE IF NOT EXISTS cities (
    id          VARCHAR(20) PRIMARY KEY,
    name        TEXT NOT NULL,
    center      GEOGRAPHY(POINT, 4326),
    bbox        GEOGRAPHY(POLYGON, 4326),
    default_zoom INT DEFAULT 12,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO cities (id, name, center, default_zoom) VALUES
    ('caba',    'Ciudad de Buenos Aires', ST_SetSRID(ST_MakePoint(-58.3816, -34.6037), 4326), 12),
    ('rosario', 'Rosario',               ST_SetSRID(ST_MakePoint(-60.6505, -32.9442), 4326), 12),
    ('cordoba', 'Córdoba',               ST_SetSRID(ST_MakePoint(-64.1811, -31.4135), 4326), 12),
    ('mendoza', 'Mendoza',               ST_SetSRID(ST_MakePoint(-68.8458, -32.8895), 4326), 12)
ON CONFLICT (id) DO NOTHING;
