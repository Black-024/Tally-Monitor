-- library.db — migración 0001.
-- Nota: la API Key y el id de usuario de Tally NO se guardan aquí (viven cifrados en credentials.dat).
CREATE TABLE data_account (
  account_id        TEXT PRIMARY KEY,                      -- UUID local
  name              TEXT NOT NULL COLLATE NOCASE UNIQUE,
  status            TEXT NOT NULL DEFAULT 'unverified'
                    CHECK (status IN ('unverified','active','key_rejected','check_failed','no_credential')),
  last_check_result TEXT                                   -- ok | auth | network | rate_limit | server | unexpected
                    CHECK (last_check_result IS NULL OR last_check_result IN
                           ('ok','auth','network','rate_limit','server','unexpected')),
  last_checked_at   TEXT,                                  -- último intento (ISO 8601 UTC)
  last_validated_at TEXT,                                  -- última validación exitosa
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE state_setting (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE app_migration_log (
  version     INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,
  applied_at  TEXT NOT NULL,
  app_version TEXT NOT NULL
);
