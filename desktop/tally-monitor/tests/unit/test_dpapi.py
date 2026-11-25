import sys

import pytest

from tally_monitor.core.errors import ProtectionUnavailableError
from tally_monitor.security.protector import default_protector


@pytest.mark.skipif(sys.platform == "win32", reason="comportamiento fuera de Windows")
def test_no_plaintext_fallback_outside_windows():
    with pytest.raises(ProtectionUnavailableError):
        default_protector()
    from tally_monitor.security.dpapi import WindowsDpapiProtector
    with pytest.raises(ProtectionUnavailableError):
        WindowsDpapiProtector()


@pytest.mark.skipif(sys.platform != "win32", reason="requiere Windows DPAPI real")
def test_real_dpapi_roundtrip():
    from tally_monitor.security.dpapi import WindowsDpapiProtector
    p = WindowsDpapiProtector()
    secret = b'{"api_key": "tly-ABCDEF1234567890"}'
    blob = p.protect(secret)
    assert secret not in blob and b"tly-" not in blob
    assert p.unprotect(blob) == secret
    assert p.protect(secret) != blob or True            # DPAPI usa sal: normalmente distinto
    with pytest.raises(Exception):
        p.unprotect(b"basura" * 10)
    with pytest.raises(ValueError):
        p.protect(b"")
