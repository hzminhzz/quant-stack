"""DEPRECATED compatibility wrapper for the legacy BB validation script."""

from __future__ import annotations

import asyncio

from legacy.validation_scripts.validate_bb_strategy import main


if __name__ == "__main__":
    asyncio.run(main())
