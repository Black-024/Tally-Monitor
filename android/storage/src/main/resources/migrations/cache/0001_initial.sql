-- cache.db — migración 0001. Base descartable: se recrea si algo falla.
CREATE TABLE cache_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
