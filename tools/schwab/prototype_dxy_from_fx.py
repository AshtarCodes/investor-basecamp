#!/usr/bin/env python3
"""PROTOTYPE (superseded): use `pnpm schwab macro dxy` for v1 USDX.

Kept for ad-hoc probing; imports production logic from schwab_cli.usdx.
"""

from __future__ import annotations

import json
import sys

from schwab_cli.macro_dxy import run_macro_dxy


def main() -> None:
    try:
        run_macro_dxy()
    except Exception as exc:  # noqa: BLE001 — prototype wrapper
        print(json.dumps({"prototype": "dxy_from_fx", "error": str(exc)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
