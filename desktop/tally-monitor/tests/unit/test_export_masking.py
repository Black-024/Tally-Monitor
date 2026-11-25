from tally_monitor.export.masking import MASK, mask_text


def test_masks_contact_data_but_keeps_dates_and_normal_text():
    t = "Escribime a juan.perez@mail.com o al +54 9 11 5555-1234, mi insta es @juanp, web www.ejemplo.com/x"
    out = mask_text(t)
    assert "juan.perez" not in out and "5555" not in out and "@juanp" not in out and "ejemplo" not in out
    assert out.count(MASK) == 4
    assert mask_text("El 12/11/2026 y el 2026-11-14 fue genial, 3 de 5") == "El 12/11/2026 y el 2026-11-14 fue genial, 3 de 5"
    assert MASK in mask_text("DNI 12.345.678")
    assert mask_text("") == ""
