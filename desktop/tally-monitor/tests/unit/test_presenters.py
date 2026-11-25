from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

from tally_monitor.ui import presenters as P

NOW = datetime(2026, 11, 11, 15, 0, 0, tzinfo=timezone.utc)


def acct(status="active", result="ok", validated="2026-11-11T14:57:00.000Z"):
    return NS(status=status, last_check_result=result, last_validated_at=validated, last_checked_at=validated)


def test_status_view_has_text_and_tone():
    assert P.status_view("active") == ("Activa", "ok")
    assert P.status_view("key_rejected") == ("Clave rechazada", "danger")
    assert P.status_view("check_failed")[1] == "warn"
    assert P.status_view("no_credential")[0] == "Sin clave guardada"
    assert P.status_view("raro")[1] == "neutral"


def test_relative_time():
    iso = lambda **k: (NOW - timedelta(**k)).strftime("%Y-%m-%dT%H:%M:%S.000Z")  # noqa: E731
    assert P.format_relative(None) == "nunca"
    assert P.format_relative(iso(seconds=10), NOW) == "hace instantes"
    assert P.format_relative(iso(minutes=3), NOW) == "hace 3 min"
    assert P.format_relative(iso(hours=2), NOW) == "hace 2 h"
    assert P.format_relative(iso(days=1), NOW) == "hace 1 día"
    assert P.format_relative(iso(days=5), NOW) == "hace 5 días"


def test_subtitle_never_mentions_key_characters():
    s = P.account_subtitle(acct(), NOW)
    assert "Activa" in s and "validada hace 3 min" in s and "Clave guardada y cifrada" in s
    assert "tly" not in s.lower()


def test_subtitle_distinguishes_causes():
    assert "Sin conexión con Tally" in P.account_subtitle(acct("check_failed", "network"), NOW)
    assert "limitó" in P.account_subtitle(acct("check_failed", "rate_limit"), NOW)
    assert "servicio de Tally" in P.account_subtitle(acct("check_failed", "server"), NOW)
    rejected = P.account_subtitle(acct("key_rejected", "auth"), NOW)
    assert "Clave rechazada" in rejected
    no_cred = P.account_subtitle(acct("no_credential", None, None), NOW)
    assert "Clave guardada" not in no_cred and "sin validar" in no_cred


def test_help_texts_do_not_call_transient_failures_invalid():
    assert "no se marcó como inválida" in P.account_help(acct("check_failed", "network"))
    assert P.account_help(acct("active")) == ""


def test_attention_and_summary():
    accts = [acct("active"), acct("key_rejected"), acct("check_failed"), acct("no_credential"), acct("unverified")]
    assert P.summarize(accts) == {"total": 5, "active": 1, "attention": 3}


def test_suggest_name_skips_taken():
    assert P.suggest_account_name([]) == "Cuenta 1"
    assert P.suggest_account_name(["Cuenta 2"]) == "Cuenta 3"
    assert P.suggest_account_name(["Cuenta 1"]) == "Cuenta 2"
    assert P.suggest_account_name(["cuenta 2", "Otra"]) == "Cuenta 3"


def test_sizes_and_reasons():
    assert P.format_size(512) == "512 B" and P.format_size(2048) == "2.0 KB" and P.format_size(3 * 1024 ** 2) == "3.0 MB"
    assert P.reason_label("pre_migracion") == "Previa a migración" and P.reason_label("x") == "x"


# ---- encuestas ----
from types import SimpleNamespace as NS  # noqa: E402

from tally_monitor.ui import presenters as P2  # noqa: E402


def _survey(**kw):
    base = dict(form_id="f", name="Encuesta", status="PUBLISHED", is_closed=False, reported_submissions=3,
                local_submissions=3, last_submission_at=None, last_synced_at="2026-11-12T12:00:00Z",
                has_new_hint=False, is_favorite=False, never_synced=False)
    base.update(kw)
    return NS(**base)


def test_survey_texts():
    now = P2._parse("2026-11-12T12:05:00Z")
    assert P2.survey_counts_text(_survey(), now) == "3 respuestas guardadas · sincronizada hace 5 min"
    assert P2.survey_counts_text(_survey(local_submissions=1), now).startswith("1 respuesta guardada")
    assert P2.survey_counts_text(_survey(never_synced=True, reported_submissions=27)) == \
        "Sin sincronizar · Tally informa 27 respuestas"
    assert P2.survey_status_text(_survey(is_closed=True)) == "Cerrada"
    assert P2.survey_status_text(_survey(status="DRAFT")) == "Borrador"


def test_filter_surveys_favorites_first_recents_in_open_order():
    a, b, c = _survey(form_id="a", name="Alfa"), _survey(form_id="b", name="Beta", is_favorite=True), \
        _survey(form_id="c", name="Gamma")
    assert [s.form_id for s in P2.filter_surveys([a, b, c])] == ["b", "a", "c"]
    assert [s.form_id for s in P2.filter_surveys([a, b, c], text="gam")] == ["c"]
    assert [s.form_id for s in P2.filter_surveys([a, b, c], mode="fav")] == ["b"]
    assert [s.form_id for s in P2.filter_surveys([a, b, c], mode="recent", recents=["c", "a"])] == ["c", "a"]


def test_sync_result_text():
    r = lambda **k: NS(**{**dict(mode="initial", new=0, updated=0, missing=0, remote_total=3, local_total=3,
                                 warnings=()), **k})
    assert P2.sync_result_text(r(new=1)) == "Se descargó 1 respuesta."
    assert P2.sync_result_text(r(new=3)) == "Se descargaron 3 respuestas."
    assert "Sin cambios" in P2.sync_result_text(r(mode="nochange"))
    assert P2.sync_result_text(r(mode="incremental", new=2)) == "2 respuestas nuevas."
    assert P2.sync_result_text(r(mode="incremental")) == "Sin respuestas nuevas."
    assert "1 ya no están en Tally" in P2.sync_result_text(r(mode="full", missing=1))
    assert "Tally informa 5" in P2.sync_result_text(r(warnings=("count_mismatch",), remote_total=5))


def test_answer_lines_and_user_search():
    ch = lambda t, o: NS(text=t, origin=o)
    ans = lambda **k: NS(**{**dict(kind="text", text="hola", is_blank=False, choices=()), **k})
    assert P2.answer_lines(ans(is_blank=True)) == ["(sin respuesta)"]
    assert P2.answer_lines(ans(kind="multi", choices=(ch("Rojo", "declared"), ch("Zzz", "other"),
                                                       ch("Q", "unmatched")))) == [
        "Rojo", "Zzz (otro)", "Q (opción que ya no existe en la encuesta)"]
    assert P2.answer_lines(ans(kind="raw", text=None)) == ["(formato de respuesta no interpretado)"]
    v = NS(label="Usuario 012")
    assert P2.response_matches(v, "012") and P2.response_matches(v, "12") and P2.response_matches(v, "")
    assert not P2.response_matches(v, "013")
    assert P2.response_matches(NS(label="Usuario A001"), "a001")


def test_response_time_is_formatted_with_seconds():
    out = P2.format_local_seconds("2026-11-12T12:34:56Z")
    assert len(out) == 19 and out[2] == "/" and out[-3] == ":"
    assert P2.format_local_seconds(None) == "—"


# ---------------- Análisis ----------------
def test_analysis_formatting_and_rows():
    from types import SimpleNamespace as NS
    assert P.format_pct(40.0) == "40,0 %" and P.format_pct(None) == "—"
    assert P.format_decimal(2.5, 2) == "2,50"
    q = NS(answered=10, blank=1, not_asked=2, other_count=2, orphan_count=1,
           options=[NS(text="Sí", count=5, pct=50.0), NS(text="No", count=0, pct=0.0)],
           other_values=[("raro", 2)])
    rows = P.bar_rows(q)
    assert rows[0] == ("Sí", 5, 0.5) and rows[1][1] == 0
    assert [r[0] for r in rows[2:]] == ["Otro (texto escrito)", "Opciones que ya no existen en la encuesta"]
    assert P.bar_value_text(5, 0.5) == "5 · 50,0 %"
    assert P.question_counts_text(q) == "10 respondieron · 1 sin respuesta · 2 no traían esta pregunta (se agregó después)"
    assert "«raro» ×2" in P.other_values_text(q)
    zero = NS(answered=0, options=[NS(text="A", count=0, pct=0.0)], other_count=0, orphan_count=0)
    assert P.bar_rows(zero) == [("A", 0, 0.0)]


def test_analysis_tiles_and_timeline_labels():
    from datetime import datetime
    from types import SimpleNamespace as NS
    o = NS(total=4, completed=3, partial=1, per_day=1.5, first_at=None, last_at=None)
    assert P.overview_tiles(o)[3] == ("Promedio por día", "1,50") and P.span_text(o) == ""
    d = datetime(2026, 3, 5, 14, 0)
    assert P.timeline_label("hour", d) == "05/03 14:00" and P.timeline_label("day", d) == "05/03"
    assert P.timeline_label("month", d) == "03/2026"
    s = NS(form_id="a", name="A", local_submissions=2), NS(form_id="b", name="B", local_submissions=0)
    assert P.survey_options(s) == [("a", "A")]


def test_summarize_args_allows_only_known_kind_values():
    from tally_monitor.services.instrumentation import summarize_args

    class R:
        def mask_account(self, a): return "Cuenta 1"
    out = summarize_args(R(), {"kind": "7d"})
    assert out["kind"] == "7d"
    assert summarize_args(R(), {"kind": "texto secreto"})["kind"] == "<valor desconocido>"
