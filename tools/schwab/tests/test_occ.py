from datetime import date

import pytest

from schwab_cli.occ import OccSymbol, parse_occ


def test_equity_symbol_strips_the_root_padding():
    assert parse_occ("IREN  270115C00055000") == OccSymbol(
        symbol="IREN  270115C00055000",
        root="IREN",
        expiry=date(2027, 1, 15),
        strike=55.0,
        right="call",
    )


def test_index_roots_keep_their_own_padding():
    xsp = parse_occ("XSP   261120P00763000")
    spxw = parse_occ("SPXW  261120C07625000")
    assert (xsp.root, xsp.strike, xsp.right) == ("XSP", 763.0, "put")
    assert (spxw.root, spxw.strike, spxw.right) == ("SPXW", 7625.0, "call")


def test_fractional_strike():
    assert parse_occ("IREN  261023P00022500").strike == 22.5


def test_a_symbol_without_padding_is_refused_with_a_one_line_message():
    with pytest.raises(ValueError, match="OCC"):
        parse_occ("IREN270115C00055000")


@pytest.mark.parametrize(
    "bad", ["", "IREN  270115X00055000", "IREN  271315C00055000", "iren  270115C00055000"]
)
def test_malformed_symbols_are_value_errors(bad):
    with pytest.raises(ValueError):
        parse_occ(bad)
