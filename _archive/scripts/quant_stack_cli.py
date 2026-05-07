#!/usr/bin/env python
"""Simple CLI wrapper - use this instead of -m quant_stack.cli.main"""

import sys
from quant_stack.cli.main import main

if __name__ == "__main__":
    sys.exit(main())