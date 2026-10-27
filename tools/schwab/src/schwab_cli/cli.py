import argparse
import json
import sys
from datetime import UTC, datetime

from schwab_cli.bitwarden_secrets import BitwardenSecretsError, load_schwab_app_credentials
from schwab_cli.capture import run_capture
from schwab_cli.http_client import schwab_get
from schwab_cli.keychain import KeychainError
from schwab_cli.lockfile import TokenLockError
from schwab_cli.macro_dxy import run_macro_dxy
from schwab_cli.oauth import OAuthError, run_login_flow
from schwab_cli.usdx import UsdxQuoteError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schwab",
        description="Schwab Trader API dev CLI for investor-basecamp.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Run Schwab OAuth login and store tokens in Keychain.")

    get_parser = sub.add_parser(
        "get",
        help="Perform one GET against api.schwabapi.com (path includes query string).",
    )
    get_parser.add_argument("path", help="API path, e.g. /trader/v1/accounts/accountNumbers")

    capture_parser = sub.add_parser(
        "capture",
        help="Pull the fixed payload set for portfolio-risk ticket 05.",
    )
    capture_parser.add_argument(
        "--option",
        required=True,
        dest="option_symbol",
        help="OCC option symbol for a contract you hold.",
    )
    capture_parser.add_argument(
        "--equity",
        required=True,
        dest="equity_ticker",
        help="Underlying equity ticker for quotes, history, and chain.",
    )

    macro_parser = sub.add_parser(
        "macro",
        help="Macro reference series (computed or external; see method/source in JSON).",
    )
    macro_sub = macro_parser.add_subparsers(dest="macro_command", required=True)
    macro_sub.add_parser(
        "dxy",
        help="ICE USDX from six Schwab FX quotes (ice-formula / schwab-fx).",
    )

    option_parser = sub.add_parser("option", help="Option pricing with our own model.")
    option_sub = option_parser.add_subparsers(dest="option_command", required=True)
    _add_option_price_parser(option_sub)
    chain = option_sub.add_parser(
        "chain", help="Every listed contract's quote and rate, as one Quote Set (read-only)."
    )
    chain.add_argument("--symbol", required=True, help="Underlying, e.g. IREN.")
    chain.add_argument("--from", dest="from_date", help="First expiry date (YYYY-MM-DD).")
    chain.add_argument("--contract-type", choices=["CALL", "PUT", "ALL"], default="CALL")

    return parser


def _add_option_price_parser(
    option_sub: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    price = option_sub.add_parser(
        "price",
        help="Reprice one option with our model: fair value now, hold to expiry, or sell early.",
    )
    price.add_argument("--symbol", required=True, help="OCC symbol, e.g. 'IREN  270115C00055000'.")
    price.add_argument(
        "--mode", choices=["theoretical", "expiry", "sell", "both"], default="theoretical"
    )
    price.add_argument("--offline", action="store_true", help="No API, no Treasury fetch.")
    price.add_argument("--spot", type=float, help="Spot at valuation (theoretical, offline).")
    price.add_argument("--vol", type=float, help="Volatility override, percent by default.")
    price.add_argument("--vol-unit", choices=["percent", "decimal"], default="percent")
    price.add_argument("--rate", type=float, help="Rate override, percent.")
    price.add_argument("--dte", type=float, help="Remaining life in days, at most the real one.")
    price.add_argument("--as-of", help="Valuation or exit date (4 pm ET) or ISO datetime.")
    price.add_argument("--expected-spot", type=float, help="Terminal spot (expiry) or exit spot.")
    price.add_argument(
        "--entry", type=float, help="P&L baseline per share; live default is the mark."
    )
    price.add_argument("--contracts", type=int, default=1)
    price.add_argument("--model", choices=["auto", "american", "european"], default="auto")
    price.add_argument("--no-div", action="store_true", help="Force zero dividends.")
    price.add_argument(
        "--div-yield", type=float, help="Continuous dividend yield override, percent."
    )


def _run_option_price(args: argparse.Namespace) -> None:
    # Imported here so `login` and `get` never load QuantLib.
    from pricing_engine import TreasuryError
    from pydantic import ValidationError

    from schwab_cli.option_price import OptionPriceArgs, run_option_price

    options = OptionPriceArgs(
        symbol=args.symbol,
        mode=args.mode,
        offline=args.offline,
        spot=args.spot,
        vol=args.vol,
        vol_unit=args.vol_unit,
        rate=args.rate,
        dte=args.dte,
        as_of=args.as_of,
        expected_spot=args.expected_spot,
        entry=args.entry,
        contracts=args.contracts,
        model=args.model,
        no_div=args.no_div,
        div_yield=args.div_yield,
    )
    try:
        output = run_option_price(options, now=datetime.now(UTC))
    except TreasuryError as error:
        raise ValueError(str(error)) from error
    except ValidationError as error:
        detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
        raise ValueError(f"the engine refused the inputs: {detail}") from error
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "login":
            client_id, client_secret = load_schwab_app_credentials()
            run_login_flow(client_id=client_id, client_secret=client_secret)
            return

        if args.command == "get":
            response = schwab_get(args.path)
            sys.stdout.write(response.text)
            if not response.text.endswith("\n"):
                sys.stdout.write("\n")
            if response.status_code >= 400:
                sys.exit(1)
            return

        if args.command == "capture":
            run_capture(
                option_symbol=args.option_symbol,
                equity_ticker=args.equity_ticker,
            )
            return

        if args.command == "macro":
            if args.macro_command == "dxy":
                run_macro_dxy()
                return
            msg = f"Unknown macro command {args.macro_command!r}"
            raise RuntimeError(msg)

        if args.command == "option":
            if args.option_command == "price":
                _run_option_price(args)
                return
            if args.option_command == "chain":
                from schwab_cli.option_chain import run_option_chain

                output = run_option_chain(
                    args.symbol,
                    now=datetime.now(UTC),
                    from_date=args.from_date,
                    contract_type=args.contract_type,
                )
                json.dump(output, sys.stdout, indent=1)
                sys.stdout.write("\n")
                return
            msg = f"Unknown option command {args.option_command!r}"
            raise RuntimeError(msg)

        msg = f"Unknown command {args.command!r}"
        raise RuntimeError(msg)
    except (
        KeychainError,
        BitwardenSecretsError,
        OAuthError,
        TokenLockError,
        UsdxQuoteError,
        ValueError,
    ) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
