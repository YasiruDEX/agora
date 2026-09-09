#!/usr/bin/env bash
# Builds (if needed) and runs the Case Management DB Agent, loading env vars from ENV_FILE
# (defaults to .env). Ballerina has no built-in dotenv support, so this is the equivalent of
# the ENV_FILE=.env.<x> pattern the Python agents use.
#
# Usage: ./run.sh                    # uses .env
#        ENV_FILE=.env.staging ./run.sh
#        LOG_LEVEL=DEBUG ./run.sh    # overrides LOG_LEVEL from the env file

set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-.env}"
LOG_LEVEL_OVERRIDE="${LOG_LEVEL:-}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    echo "Warning: $ENV_FILE not found — relying on already-exported env vars." >&2
fi
# An inline LOG_LEVEL=... on the command line should beat the env file, not the other way
# round; sourcing above would otherwise have clobbered it.
if [ -n "$LOG_LEVEL_OVERRIDE" ]; then
    LOG_LEVEL="$LOG_LEVEL_OVERRIDE"
fi

# ballerina/log's level is a configurable, not an env var. Only set it when Config.toml isn't
# providing one, so a committed Config.toml stays authoritative.
if [ -n "${LOG_LEVEL:-}" ] && [ ! -f Config.toml ]; then
    export BAL_CONFIG_VAR_BALLERINA_LOG_LEVEL="$LOG_LEVEL"
fi

if [ -z "${JAVA_HOME:-}" ] && command -v brew >/dev/null 2>&1; then
    export JAVA_HOME="$(brew --prefix openjdk)"
fi

JAR="target/bin/case_management_db_agent.jar"
if [ ! -f "$JAR" ]; then
    bal build
fi

exec "${JAVA_HOME:+$JAVA_HOME/bin/}java" -jar "$JAR"
