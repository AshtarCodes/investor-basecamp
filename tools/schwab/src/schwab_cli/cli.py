import argparse
import sys

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

    return parser


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
