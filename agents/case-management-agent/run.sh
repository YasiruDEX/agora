#!/usr/bin/env bash
# Builds (if needed) and runs the Case Management Agent, loading env vars from ENV_FILE
# (defaults to .env). Ballerina has no built-in dotenv support, so this is the equivalent of
# the ENV_FILE=.env.<x> pattern the Python agents use.
#
# Usage: ./run.sh          # uses .env
#        ENV_FILE=.env.staging ./run.sh

set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    echo "Warning: $ENV_FILE not found — relying on already-exported env vars." >&2
fi

if [ -z "${JAVA_HOME:-}" ] && command -v brew >/dev/null 2>&1; then
    export JAVA_HOME="$(brew --prefix openjdk)"
fi

JAR="target/bin/case_management_agent.jar"
if [ ! -f "$JAR" ]; then
    bal build
fi

exec "${JAVA_HOME:+$JAVA_HOME/bin/}java" -jar "$JAR"
