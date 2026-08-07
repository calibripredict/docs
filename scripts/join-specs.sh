#!/usr/bin/env bash
# Merges the per-service specs into the single document Mintlify renders.
#
#   ./scripts/join-specs.sh
#
# WHY A JOIN. The API is one surface to a caller and several services to us:
# market data answers from the engine, order placement and account data from the
# orchestrator, sign-in and verification from the identity service. A reader does
# not care which, and should not have to pick a tab to find out whether "list
# markets", "sign in" and "place an order" live in the same API. They do.
#
# The per-service files stay the source of truth — each is generated in its own
# repo, drift-checked there, and synced here by that repo's CI. This script only
# combines them, and calibri.yaml is the combined output. Editing any of the
# three by hand is undone on the next sync.
#
# All inputs must be the SAME OpenAPI version or the join refuses — correctly,
# since 3.0 and 3.1 express nullability incompatibly. All three are 3.1.
set -euo pipefail

cd "$(dirname "$0")/.."

SPECS_DIR="api-reference/openapi"
OUT="${SPECS_DIR}/calibri.yaml"

inputs=()
for f in "${SPECS_DIR}"/public.yaml "${SPECS_DIR}"/account.yaml "${SPECS_DIR}"/identity.yaml; do
  [ -f "$f" ] || { echo "missing ${f}" >&2; exit 1; }
  inputs+=("$f")
done

# without-x-tag-groups: we deliberately share the "Market" tag across the
# engine and orchestrator specs so the joined reference has one Market section.
# Redocly's default would prefix-group tags by file and refuse the name clash.
npx --yes @redocly/cli@latest join "${inputs[@]}" \
  --without-x-tag-groups \
  -o "${OUT}"

# The join writes an `info` block from the first input. We rewrite info + tags
# so folders match Polymarket-style resource groups (Events, Markets, Trade…).
# Mintlify ignores x-tagGroups — tag names become sidebar folders.
#
# Line-oriented only — never a greedy regex that can swallow `paths:`.
python3 - "${OUT}" <<'PY'
import sys

path = sys.argv[1]
lines = open(path).read().splitlines(keepends=True)

def is_top_level(line: str) -> bool:
    return bool(line) and not line[0].isspace() and line != "\n"

# Polymarket-style resource order: discover → market data → trade → account.
preferred = [
    "Health",
    "Events",
    "Markets",
    "Series",
    "Tags",
    "Market Data",
    "Assets",
    "Community",
    "Currencies",
    "Trade",
    "Positions",
    "Wallet",
    "Rewards",
    "Account",
]

found: set[str] = set()
for i, line in enumerate(lines):
    if line.rstrip("\n") in ("      tags:", "        tags:"):
        j = i + 1
        while j < len(lines):
            s = lines[j].rstrip("\n")
            if s.startswith("      - ") or s.startswith("        - "):
                found.add(s.split("- ", 1)[1].strip())
                j += 1
                continue
            break

ordered = [t for t in preferred if t in found]
for t in sorted(found):
    if t not in ordered:
        ordered.append(t)

descriptions = {
    "Health": "Service liveness.",
    "Events": "Discover events and their metadata.",
    "Markets": "List markets and load market detail for trading.",
    "Series": "Recurring event series.",
    "Tags": "Editorial shelves used to browse the catalogue.",
    "Market Data": "Order book, depth, trade tape, tickers, and candles.",
    "Assets": "Underlying asset price history for price-feed markets.",
    "Community": "Leaderboard and platform activity.",
    "Currencies": "Currency registry.",
    "Trade": "Place, list, and cancel orders.",
    "Positions": "Your matched contracts.",
    "Wallet": "Self-custody Safe, passkey, session keys, and relay.",
    "Rewards": "Maker rebates and referral earnings.",
    "Account": "Balances, ledger, PnL, limits, preferences, and profile.",
}

info_lines = [
    "info:\n",
    "  title: Calibri API\n",
    "  version: '1.0.0'\n",
    "  description: >-\n",
    "    The Calibri API. Discover markets, read live books, place signed orders,\n",
    "    and manage positions and account data.\n",
    "\n",
    "    Routed by path prefix to the service that answers it — which is an\n",
    "    implementation detail, not something a caller has to reason about.\n",
]
tags_lines = ["tags:\n"]
for t in ordered:
    tags_lines += [
        f"  - name: {t}\n",
        f"    description: {descriptions.get(t, t)}\n",
        f"    x-displayName: {t}\n",
    ]

# --- rebuild: replace top-level info / tags; drop x-tagGroups (unused by Mintlify) ---
out: list[str] = []
i = 0
replaced_info = False
replaced_tags = False
while i < len(lines):
    line = lines[i]
    if line.startswith("info:"):
        out.extend(info_lines)
        replaced_info = True
        i += 1
        while i < len(lines) and not is_top_level(lines[i]):
            i += 1
        continue
    if line.startswith("tags:"):
        out.extend(tags_lines)
        replaced_tags = True
        i += 1
        while i < len(lines) and not is_top_level(lines[i]):
            i += 1
        continue
    if line.startswith("x-tagGroups:"):
        i += 1
        while i < len(lines) and not is_top_level(lines[i]):
            i += 1
        continue
    out.append(line)
    i += 1

if not replaced_info:
    sys.exit("join output had no info block — the merge probably failed")
if not replaced_tags:
    sys.exit("join output had no tags block")

open(path, "w").writelines(out)
if sum(1 for l in out if l.startswith("paths:")) != 1:
    sys.exit("postprocess lost the paths block — refusing to write a hollow doc")
PY

echo "wrote ${OUT}"
npx --yes @redocly/cli@latest lint "${OUT}"
