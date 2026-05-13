#!/usr/bin/env python3
"""
Thin wrapper that allows running the simulation directly:

    python copilot.py --input <dir> --output <dir>

or, after making this file executable:

    ./copilot.py --input <dir> --output <dir>
"""

import sys
from copilot.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
