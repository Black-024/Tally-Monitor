from datetime import datetime
from types import SimpleNamespace as NS

from tally_monitor.ui import presenters as P
from tally_monitor.ui.greeting import greeting_for


def sv(fid, local=0, reported=None, last=None, closed=False, hint=None):
    return NS(form_id=fid, name=fid, local_submissions=local, reported_submissions=reported, last_submission_at=last,
              is_closed=closed, has_new_hint=(reported is not None and reported > local) if hint is None else hint,
              never_synced=False)


def test_greeting_special_days():
    assert "Navidad" in greeting_for(datetime(2026, 12, 25, 10))[0]
    assert "navideñas" in greeting_for(datetime(2026, 12, 24, 20))[1]
    assert "año nuevo" in greeting_for(datetime(2027, 1, 1, 9))[0]
    assert "Halloween" in greeting_for(datetime(2026, 10, 31, 9))[0]


def test_greeting_time_of_day_and_weekday():
    assert greeting_for(datetime(2026, 11, 16, 8))[0] == "¡Buen día!"                    # lunes
    assert greeting_for(datetime(2026, 11, 16, 8))[1].startswith("Arrancó la semana")
    assert greeting_for(datetime(2026, 11, 20, 15))[0] == "¡Buenas tardes!"               # viernes
    assert greeting_for(datetime(2026, 11, 20, 22))[0] == "¡Buenas noches!"
    assert greeting_for(datetime(2026, 11, 21, 3))[0].startswith("Trasnochando")


def test_greeting_never_empty_any_day():
    from datetime import timedelta
    d = datetime(2026, 1, 1, 0)
    for i in range(366 * 24 // 5):
        t, s = greeting_for(d + timedelta(hours=5 * i))
        assert t and s


def test_home_overview_counts_and_pending():
    per = [("a", [sv("f1", 10, 12, "2026-11-10T10:00:00.000Z"), sv("f2", 5, 5, "2026-11-12T10:00:00.000Z", closed=True)]),
           ("b", [sv("f3", 1, 4, "2026-11-01T10:00:00.000Z")])]
    ov = P.home_overview(per)
    assert (ov.survey_count, ov.response_total, ov.open_count) == (3, 16, 2)
    assert ov.new_count == 5 and [(a, s.form_id) for a, s in ov.pending] == [("a", "f1"), ("b", "f3")]
    assert ov.last_at == "2026-11-12T10:00:00.000Z"
    assert [s.form_id for _a, s in ov.top] == ["f2", "f1", "f3"]


def test_home_overview_empty():
    ov = P.home_overview([])
    assert ov.survey_count == 0 and ov.pending == () and ov.last_at is None and ov.new_count == 0
