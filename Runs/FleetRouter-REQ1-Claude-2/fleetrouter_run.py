#!/usr/bin/env python3
"""Wrapper to run fleetrouter from /workspace."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetrouter.main import main
main()
