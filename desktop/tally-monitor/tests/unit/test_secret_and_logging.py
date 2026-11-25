import copy
import json
import logging
import pickle

import pytest

from tally_monitor.core.errors import TallyMonitorError
from tally_monitor.core.logging_setup import setup_logging
from tally_monitor.core.redact import redact
from tally_monitor.core.secret import SecretStr

KEY = "tly-SECRETSECRET1234567890"


def test_secret_never_printed():
    s = SecretStr(KEY)
    assert KEY not in str(s) and KEY not in repr(s) and KEY not in f"{s}" and KEY not in "%s" % s
    assert KEY not in format(s, ">20") and KEY not in repr([s]) and KEY not in repr({"k": s})
    assert s.reveal() == KEY and len(s) == len(KEY)


def test_secret_not_serializable():
    s = SecretStr(KEY)
    with pytest.raises(TypeError):
        json.dumps({"k": s})
    for f in (pickle.dumps, copy.copy, copy.deepcopy):
        with pytest.raises(TypeError):
            f(s)
    with pytest.raises(TypeError):
        hash(s)
    with pytest.raises(AttributeError):
        s._value = "x"


def test_secret_equality_is_explicit():
    assert SecretStr(KEY).matches(SecretStr(KEY))
    assert not SecretStr(KEY).matches(SecretStr(KEY + "x"))
    assert (SecretStr(KEY) == SecretStr(KEY)) is False   # no se compara con == por accidente


def test_redact():
    assert KEY not in redact(f"fallo con {KEY} y Bearer {KEY}")
    assert redact("sin claves") == "sin claves"


def test_error_messages_redacted():
    e = TallyMonitorError(f"algo con {KEY}")
    assert KEY not in e.user_message and KEY not in str(e)


def test_log_file_never_contains_key(tmp_path):
    logger = setup_logging(tmp_path, "DEBUG")
    logger.info("mensaje %s", KEY)
    logger.info("dict %r", {"k": KEY})
    try:
        raise RuntimeError(f"fallo {KEY}")
    except RuntimeError:
        logger.exception("explotó %s", KEY)
    logging.getLogger("tally_monitor.x").error("hijo %s", KEY)
    for h in logger.handlers:
        h.flush()
    text = (tmp_path / "tally_monitor.log").read_text(encoding="utf-8")
    assert KEY not in text and "SECRETSECRET" not in text
    assert "explotó" in text
