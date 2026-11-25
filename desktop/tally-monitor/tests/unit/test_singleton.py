from tally_monitor.core.singleton import SingleInstance


def test_second_instance_is_refused_until_released(tmp_path):
    a, b = SingleInstance(tmp_path / "x.lock"), SingleInstance(tmp_path / "x.lock")
    assert a.acquire()
    assert not b.acquire()
    a.release()
    assert b.acquire()
    b.release()


def test_unwritable_location_never_blocks_startup(tmp_path):
    f = tmp_path / "archivo"
    f.write_text("x")
    assert SingleInstance(f / "sub" / "x.lock").acquire()
