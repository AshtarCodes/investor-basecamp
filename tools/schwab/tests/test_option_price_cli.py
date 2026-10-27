import json
import sys

import pytest

from schwab_cli.cli import main

OFFLINE = [
    "option", "price", "--symbol", "XSP   261120C00700000", "--offline", "--model", "european",
    "--spot", "700", "--vol", "20", "--rate", "4", "--as-of", "2026-10-26",
]  # fmt: skip


def test_offline_theoretical_prints_json_on_stdout(capsys):
    main(OFFLINE)
    out = json.loads(capsys.readouterr().out)
    assert out["contract"]["underlying"] == "XSP"
    assert out["results"]["theoretical"]["ours"]["value"] > 0


def test_user_errors_are_one_line_on_stderr_with_exit_1(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["option", "price", "--symbol", "NDX   261120C20000000", "--offline", "--model",
              "european", "--spot", "20000", "--vol", "20", "--rate", "4"])  # fmt: skip
    assert exit_info.value.code == 1
    err = capsys.readouterr().err.strip()
    assert "NDX" in err and "\n" not in err


def test_engine_validation_errors_are_one_line_too(capsys):
    with pytest.raises(SystemExit):
        main([*OFFLINE[:-2], "--spot", "-5", "--as-of", "2026-10-26"])
    err = capsys.readouterr().err.strip()
    assert "\n" not in err and "spot" in err


def test_login_and_get_do_not_load_quantlib():
    import subprocess

    code = (
        "import sys; import schwab_cli.cli as c; c._build_parser();"
        "sys.exit(1 if 'QuantLib' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_option_chain_is_a_command(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["option", "chain", "--help"])
    assert exit_info.value.code == 0
    assert "--contract-type" in capsys.readouterr().out
