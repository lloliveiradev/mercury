#!/bin/bash
# Copy the emulator CA before the server drops privileges. The source is mode 600
# on the host and is replaced whenever the emulator starts.
set -euo pipefail
install -m 0644 -o clickhouse -g clickhouse \
    /run/emulator-ca/ca.pem /etc/clickhouse-server/emulator-ca.pem
exec /entrypoint.sh "$@"
