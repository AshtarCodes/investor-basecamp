"""Where a failure is logged: only the worker and pool modules write to stderr, never `errors.py`.

These are unit tests of `error_of` and `price_contract_safely`. No request makes a pool
process fail with `internal` (the engine raises nothing unexpected for any input we can build), and
patching a spawned pool process needs a hook, so the spawned-process tests cannot reach them.
"""

from datetime import UTC, datetime

from support import request, src

import pricing_engine.pool as pool_module
from pricing_engine.batch import SHOCK_NUMERICS, BatchContract, Shock
from pricing_engine.errors import error_of
from pricing_engine.pool import price_contract_safely


def contract_of(**options) -> BatchContract:
    base = request(sigma=None, mark=src(5.0), **options)
    return BatchContract(request=base, shocks=[Shock(spot_move=0.0, iv_shift=0.0, days_forward=0)])


def test_error_of_only_builds_the_error_and_writes_nothing(capsys):
    failure = error_of(RuntimeError("boom"))

    assert (failure.code, failure.message) == ("internal", "RuntimeError: boom")
    assert capsys.readouterr().err == ""


def test_a_contract_that_fails_unexpectedly_is_logged_with_its_identity_and_reported(
    monkeypatch, capsys
):
    def explode(contract, mode, numerics):
        raise RuntimeError("boom")

    monkeypatch.setattr(pool_module, "price_contract", explode)

    failed = price_contract_safely(contract_of(), "absolute", SHOCK_NUMERICS)

    assert failed.ok is False and failed.error.code == "internal"
    logged = capsys.readouterr().err
    assert "RuntimeError: boom" in logged and "SPY" in logged


def test_a_contract_with_an_unsupported_root_is_a_model_error_and_is_not_logged(capsys):
    valuation = datetime(2026, 10, 26, 14, 0, tzinfo=UTC)
    unsupported = contract_of(root="NDX", valuation=valuation)

    failed = price_contract_safely(unsupported, "absolute", SHOCK_NUMERICS)

    assert failed.ok is False and failed.error.code == "model_error"
    assert capsys.readouterr().err == ""
