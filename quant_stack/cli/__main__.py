"""Entry point for `python -m quant_stack.cli`."""

from __future__ import annotations

import sys

from quant_stack.cli.main import main


if __name__ == "__main__":
    sys.exit(main())
