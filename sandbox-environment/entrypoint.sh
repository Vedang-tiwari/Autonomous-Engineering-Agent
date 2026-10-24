#!/usr/bin/env bash
set -e

# Autonomous Engineering Agent Sandbox Entrypoint
# Enforces clean working directory and execution boundary

if [ "$#" -eq 0 ]; then
    exec /bin/bash
else
    exec "$@"
fi
