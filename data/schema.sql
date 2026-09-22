CREATE TABLE sectors_cache (cache_key TEXT PRIMARY KEY, endpoint TEXT NOT NULL, fetched_at REAL NOT NULL, expires_at REAL NOT NULL, payload_json TEXT NOT NULL);
