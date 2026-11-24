#!/usr/bin/env bash
# Expected to FAIL in a zero-egress environment (private VPC, NetworkPolicy, or isolated compose).
# A successful curl means the perimeter is not closed.
set -euo pipefail

URL="${EGRESS_PROBE_URL:-https://example.com}"
if curl --max-time 5 --silent --show-error --output /dev/null "$URL"; then
  echo "egress-smoke: unexpected success reaching $URL" >&2
  exit 1
fi
echo "egress-smoke: no public egress to $URL (as expected)"
