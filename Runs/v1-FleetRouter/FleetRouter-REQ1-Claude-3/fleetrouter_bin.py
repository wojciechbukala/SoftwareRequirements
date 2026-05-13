#!/usr/bin/env python3
"""Wrapper script so fleetrouter can be run as 'python3 fleetrouter_bin.py'."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleetrouter.main import main
main()
