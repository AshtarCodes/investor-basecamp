"""`option chain` against the replayed IREN chain: one read-only GET, mapped to a Quote Set."""

from urllib.parse import parse_qs, urlparse

import pytest
from schwab_fakes import FakeSchwab, now_for, treasury_curves

from schwab_cli.option_chain import run_option_chain


def run(*, curves=None, **flags):
    fake = FakeSchwab("iren")
    out = run_option_chain("IREN", now=now_for("iren"), get=fake, curves=curves or treasury_curves(), **flags)
    return out, fake


def test_one_chain_get_for_the_calls_from_a_date():
    _, fake = run(from_date="2027-01-01")
    assert len(fake.paths) == 1
    query = {k: v[0] for k, v in parse_qs(urlparse(fake.paths[0]).query).items()}
    assert fake.paths[0].startswith("/marketdata/v1/chains?")
    assert query == {"symbol": "IREN", "contractType": "CALL", "fromDate": "2027-01-01"}


def test_each_contract_carries_its_quote_and_the_underlying_spot():
    out, _ = run()
    assert out["symbol"] == "IREN"
    assert out["spot"] == 25.22
    [call] = out["contracts"]
    assert call["occ"] == "IREN  270115C00025000"
    assert (call["expiry"], call["strike"], call["kind"]) == ("2027-01-15", 25.0, "C")
    assert (call["bid"], call["ask"], call["mark"], call["delta"]) == (4.8, 5.15, 4.97, 0.596)
    assert call["iv"] == 99.697  # Schwab's, percent
    assert call["spot"] == 25.22
    assert call["quoteTime"].startswith("2026-10-26")
    assert out["takenAt"] == now_for("iren").isoformat()


def test_the_rate_is_the_treasury_rate_for_each_expiry_in_percent():
    out, _ = run()
    rate = out["contracts"][0]["rate"]
    assert 3.5 < rate < 5
    assert out["rates"]["2027-01-15"] == {"value": rate, "from": "treasury-gov", "curveDate": "2026-10-23"}


def test_without_a_treasury_curve_the_chains_interest_rate_is_used_and_flagged():
    out, _ = run(curves=treasury_curves(fail=True))
    assert out["contracts"][0]["rate"] == pytest.approx(4.043)
    assert out["rates"]["2027-01-15"]["from"] == "schwab-chain-fallback"
    assert out["warnings"] == ["no Treasury curve: the rate is Schwab's chain interestRate"]
