#!/bin/bash
# Double-click in Finder (or run in Terminal) to start myDB from source.
cd "$(dirname "$0")"
exec .venv/bin/python myDB.py "$@"
