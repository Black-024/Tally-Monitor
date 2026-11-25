-- library.db — migración 0003: datos propios del usuario sobre cada encuesta (meta, nota, etiquetas, archivada).
-- Son datos locales sin credenciales: entran en las copias de seguridad. Se borran con la cuenta o la encuesta (ON DELETE CASCADE).
CREATE TABLE survey_meta (
  account_id TEXT NOT NULL,
  form_id TEXT NOT NULL,
  goal INTEGER CHECK (goal IS NULL OR (goal >= 1 AND goal <= 1000000)),
  note TEXT NOT NULL DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
  PRIMARY KEY (account_id, form_id),
  FOREIGN KEY (account_id, form_id) REFERENCES data_form(account_id, form_id) ON DELETE CASCADE
);
CREATE TABLE survey_tags (
  account_id TEXT NOT NULL,
  form_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  PRIMARY KEY (account_id, form_id, tag),
  FOREIGN KEY (account_id, form_id) REFERENCES data_form(account_id, form_id) ON DELETE CASCADE
);
