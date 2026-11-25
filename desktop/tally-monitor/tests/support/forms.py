"""Construye un formulario falso con las formas reales de Tally (confirmadas contra la API real)."""
FORM_ID = "AbC123"
Q_SINGLE, Q_MULTI, Q_TEXT = "q-single", "q-multi", "q-text"
OPTS_SINGLE = ["Sí", "No", "Otro"]
OPTS_MULTI = ["Rojo", "Verde", "Azul"]


def _blocks():
    def opt(group, text, i, kind="MULTIPLE_CHOICE_OPTION", other=False):
        p = {"index": i, "isRequired": True, "text": text}
        if other:
            p["hasOtherOption"] = True
        return {"type": kind, "groupType": "MULTIPLE_CHOICE" if "MULTIPLE" in kind else "CHECKBOXES",
                "uuid": f"{group}-{i}", "groupUuid": group, "payload": p}
    blocks = [{"type": "FORM_TITLE", "groupType": "TEXT", "uuid": "t0", "groupUuid": "gt",
               "payload": {"title": "Encuesta", "safeHTMLSchema": [["Encuesta"]]}}]
    blocks += [opt("g-single", t, i, other=(t == "Otro")) for i, t in enumerate(OPTS_SINGLE)]
    blocks += [opt("g-multi", t, i, "CHECKBOX") for i, t in enumerate(OPTS_MULTI)]
    blocks.append({"type": "TEXTAREA", "groupType": "TEXTAREA", "uuid": "g-text-0", "groupUuid": "g-text",
                   "payload": {"isRequired": False, "placeholder": "..."}})
    return blocks


def _question(qid, title, qtype, group):
    return {"id": qid, "formId": FORM_ID, "title": title, "type": qtype, "isDeleted": False,
            "numberOfResponses": 0, "createdAt": "2026-11-01T00:00:00.000Z", "updatedAt": "2026-11-01T00:00:00.000Z",
            "isTitleModifiedByUser": False,
            "fields": [{"blockGroupUuid": group, "questionType": qtype, "title": title, "type": qtype, "uuid": group + "-0"}]}


def submission(n, *, single="Sí", multi=("Rojo",), text="hola", completed=True, sid=None):
    """n = minuto del día 2026-11-10 (da fechas crecientes y únicas)."""
    ts = f"2026-11-10T{n // 60:02d}:{n % 60:02d}:00.000Z"
    sid = sid or f"sub{n:04d}"

    def resp(qid, ans):
        return {"id": f"r-{sid}-{qid}", "formId": FORM_ID, "questionId": qid, "respondentId": "RESP-SECRET",
                "submissionId": sid, "sessionUuid": "SESSION-SECRET", "answer": ans, "createdAt": ts, "updatedAt": ts}
    return {"id": sid, "formId": FORM_ID, "respondentId": "RESP-SECRET", "locale": "es", "isCompleted": completed,
            "submittedAt": ts, "createdAt": ts, "updatedAt": ts, "previewUrl": "https://tally.so/preview/SECRET",
            "pdfUrl": "https://tally.so/pdf/SECRET",
            "responses": [resp(Q_SINGLE, [single] if single else None), resp(Q_MULTI, list(multi) if multi else None),
                          resp(Q_TEXT, text)]}


def add_form(tally, submissions, form_id=FORM_ID, name="Mi encuesta"):
    summary = {"id": form_id, "name": name, "isNameModifiedByUser": True, "workspaceId": "w1", "folderId": None,
               "organizationId": "o1", "createdByUserId": "u1", "status": "PUBLISHED", "hasDraftBlocks": False,
               "numberOfSubmissions": len(submissions), "createdAt": "2026-11-01T00:00:00.000Z",
               "updatedAt": "2026-11-09T00:00:00.000Z", "index": 0, "isClosed": False}
    questions = {"hasResponses": True, "questions": [
        _question(Q_SINGLE, "¿Te gustó?", "MULTIPLE_CHOICE", "g-single"),
        _question(Q_MULTI, "Colores", "CHECKBOXES", "g-multi"),
        _question(Q_TEXT, "Comentarios", "TEXTAREA", "g-text")]}
    tally.forms[form_id] = {"summary": summary, "detail": {**summary, "blocks": _blocks(), "settings": {"x": 1}},
                            "questions": questions,
                            "submissions": sorted(submissions, key=lambda s: s["submittedAt"], reverse=True)}
    return tally.forms[form_id]


def push(tally, sub, form_id=FORM_ID):
    f = tally.forms[form_id]
    f["submissions"].insert(0, sub)
    f["summary"]["numberOfSubmissions"] = f["detail"]["numberOfSubmissions"] = len(f["submissions"])
    f["submissions"].sort(key=lambda s: s["submittedAt"], reverse=True)


def big_submission(i, *, text_every=3):
    """Envío n.º i para pruebas de carga: fechas únicas y crecientes durante muchos días (i = 0, 1, 2…)."""
    import datetime as _dt
    ts_dt = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc) + _dt.timedelta(minutes=i * 7)
    ts = ts_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    sid = f"big{i:07d}"
    singles = ["Sí", "No", "Otro"]
    multis = [("Rojo",), ("Verde", "Azul"), ("Rojo", "Verde", "Azul"), ()]

    def resp(qid, ans):
        return {"id": f"r-{sid}-{qid}", "formId": FORM_ID, "questionId": qid, "respondentId": "RESP-SECRET",
                "submissionId": sid, "sessionUuid": "SESSION-SECRET", "answer": ans, "createdAt": ts, "updatedAt": ts}
    text = f"comentario {i} con algo de texto para que pese un poco" if i % text_every == 0 else None
    return {"id": sid, "formId": FORM_ID, "respondentId": "RESP-SECRET", "locale": "es", "isCompleted": i % 17 != 0,
            "submittedAt": ts, "createdAt": ts, "updatedAt": ts, "previewUrl": "https://tally.so/preview/SECRET",
            "pdfUrl": "https://tally.so/pdf/SECRET",
            "responses": [resp(Q_SINGLE, [singles[i % 3]]), resp(Q_MULTI, list(multis[i % 4]) or None),
                          resp(Q_TEXT, text)]}
