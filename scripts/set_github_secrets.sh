#!/usr/bin/env bash
# Sets the GitHub Actions repo secrets this repo's CI actually consumes.
#
# Run this yourself: it reads .env.local from your own machine (nothing in
# this Claude Code session is able to read that file, by design), so this
# script must be executed by you, not by the agent.
#
#   bash scripts/set_github_secrets.sh
#
# Deliberately does NOT set HEDERA_PRIVATE_KEY or ENS_PRIVATE_KEY as GitHub
# secrets: nothing in .github/workflows/ consumes either one today (only
# verify-checklist.mjs reads GRAPH_API_KEY), so putting a key that controls
# real funds/identity into CI would be pure added exposure with zero
# benefit. The live scripts (scripts/live_smoke_test.py,
# scripts/register_agents_live.py) read those two straight from your local
# environment when you run them yourself. If you deliberately want them in
# GitHub secrets anyway (e.g. you're about to wire a live CI check for
# Hedera/ENS the same way verify-checklist.mjs does for Graph), uncomment
# the two lines at the bottom -- don't do it "just in case."

set -euo pipefail
cd "$(dirname "$0")/.."

REPO="arrnaya/AgentRIA"
ENV_FILE=".env.local"

if [ ! -f "$ENV_FILE" ]; then
  echo "No $ENV_FILE found in $(pwd) -- nothing to read." >&2
  exit 1
fi

set_secret() {
  local name="$1"
  # Read the value for $name out of .env.local without ever printing it.
  local value
  value="$(grep -E "^${name}=" "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)"
  if [ -z "$value" ]; then
    echo "  skip $name (not set in $ENV_FILE)"
    return
  fi
  # No -b/--body flag: gh reads the secret value from stdin by default.
  printf '%s' "$value" | gh secret set "$name" --repo "$REPO"
  echo "  set  $name"
}

echo "Setting GitHub Actions secrets for $REPO from $ENV_FILE ..."

# Consumed today by .github/scripts/verify-checklist.mjs:
set_secret GRAPH_API_KEY

# Not consumed by any workflow yet, but harmless config (no funds/identity
# risk) -- safe to store now if you're planning to wire a live-verification
# job for the Hedera lane next:
set_secret ANTHROPIC_API_KEY
set_secret ETHERSCAN_API_KEY
set_secret COINGECKO_API_KEY
set_secret BLOCKY402_FACILITATOR_URL
set_secret SEPOLIA_RPC_URL
set_secret ENS_RESOLVER_ADDRESS
set_secret HEDERA_ACCOUNT_ID

# NOT listed here on purpose: HCS_TOPIC_ID doesn't exist yet until you
# create it -- it's not a credential you obtain ahead of time, it's the
# *output* of a one-time on-chain call. Run HcsLogger.create_topic() once
# (needs HEDERA_ACCOUNT_ID/HEDERA_PRIVATE_KEY in your local environment),
# it prints back a topic id like "0.0.123456", then add THAT to
# .env.local as HCS_TOPIC_ID and re-run this script if you want it as a
# secret too.

# Deliberately NOT set by default -- see the header comment above.
# set_secret HEDERA_PRIVATE_KEY
# set_secret ENS_PRIVATE_KEY

echo "Done. Verify with: gh secret list --repo $REPO"
