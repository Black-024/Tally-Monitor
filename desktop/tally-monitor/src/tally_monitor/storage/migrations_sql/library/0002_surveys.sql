-- library.db — migración 0002 : encuestas y envíos.
-- Tres capas: raw_* («JSON original sanitizado»), data_* (normalizado, reconstruible desde raw_*)
-- y state_* (estado persistente que NO se puede reconstruir). Nada de aquí contiene API Keys.
-- Al eliminar una cuenta se borra todo lo suyo (ON DELETE CASCADE).

CREATE TABLE raw_form (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  sanitized_json TEXT NOT NULL,          -- {"summary": {...}|null, "detail": {...}|null}
  sanitizer_version INTEGER NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (account_id, form_id)
);
CREATE TABLE raw_questions (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  sanitized_json TEXT NOT NULL,
  sanitizer_version INTEGER NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (account_id, form_id)
);
CREATE TABLE raw_submission (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  submission_id TEXT NOT NULL,
  form_id TEXT NOT NULL,
  sanitized_json TEXT NOT NULL,
  sanitizer_version INTEGER NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  missing_at_source_at TEXT,
  PRIMARY KEY (account_id, submission_id)
);
CREATE INDEX idx_raw_submission_form ON raw_submission(account_id, form_id);

CREATE TABLE data_form (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  is_closed INTEGER NOT NULL DEFAULT 0,
  workspace_id TEXT,
  reported_submissions INTEGER,          -- lo que informa Tally
  created_at TEXT,
  updated_at TEXT,
  last_submission_at TEXT,
  last_synced_at TEXT,
  PRIMARY KEY (account_id, form_id)
);
CREATE TABLE data_question (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  reported_responses INTEGER,
  group_uuid TEXT,
  has_other_option INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (account_id, form_id, question_id)
);
CREATE TABLE data_option (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  option_text TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (account_id, form_id, question_id, option_text)
);
CREATE TABLE data_submission (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  submission_id TEXT NOT NULL,
  form_id TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  is_completed INTEGER NOT NULL DEFAULT 1,
  created_at TEXT,
  updated_at TEXT,
  missing_at_source_at TEXT,
  PRIMARY KEY (account_id, submission_id)
);
CREATE INDEX idx_data_submission_form ON data_submission(account_id, form_id, submitted_at);
CREATE TABLE data_answer (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  submission_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('text','single','multi','raw')),
  text_value TEXT,
  is_blank INTEGER NOT NULL DEFAULT 0,
  raw_json TEXT NOT NULL,
  PRIMARY KEY (account_id, submission_id, question_id)
);
CREATE TABLE data_choice (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  submission_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  option_text TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('declared','other','unmatched')),
  PRIMARY KEY (account_id, submission_id, question_id, option_text)
);

CREATE TABLE state_user_number (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  submission_id TEXT NOT NULL,
  number INTEGER NOT NULL CHECK (number >= 1),
  PRIMARY KEY (account_id, submission_id),
  UNIQUE (account_id, form_id, number)
);
CREATE TABLE state_form_counter (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  next_number INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (account_id, form_id)
);
CREATE TABLE state_favorite (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  PRIMARY KEY (account_id, form_id)
);
CREATE TABLE state_recent (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  opened_at TEXT NOT NULL,
  PRIMARY KEY (account_id, form_id)
);
CREATE TABLE state_sync (
  account_id TEXT NOT NULL REFERENCES data_account(account_id) ON DELETE CASCADE,
  form_id TEXT NOT NULL,
  newest_submitted_at TEXT,              -- marca de completitud: solo avanza cuando una sincronización termina
  newest_submission_id TEXT,
  last_sync_at TEXT,
  last_full_reconcile_at TEXT,
  last_error TEXT,
  PRIMARY KEY (account_id, form_id)
);
