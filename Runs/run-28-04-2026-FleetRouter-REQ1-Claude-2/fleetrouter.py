#!/usr/bin/env python3
"""FleetRouter standalone script."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetrouter.main import main
main()
