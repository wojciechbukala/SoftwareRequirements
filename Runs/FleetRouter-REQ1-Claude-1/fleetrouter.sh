#!/bin/sh
# Wrapper to invoke FleetRouter from the workspace directory.
exec python3 -m fleetrouter.main "$@"
