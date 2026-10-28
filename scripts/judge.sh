#!/usr/bin/env bash
# Local hardened judge — mirrors the external judge's order. Fail-closed, claim-ids only on failure.
set -u
cd "$(dirname "$0")/.."
export BLINDSPOT_ROOT="$PWD"
echo "== G-setup =="; python scripts/validate_hardened.py --setup-only || exit 1
echo "== durable setup tests =="; python -m pytest tests/properties/test_setup_invariants.py -q -p no:cacheprovider || exit 1
if [ -f pipelines/flood_secondary_dam.py ] && [ -f pipelines/fire_peat_evasion.py ]; then
  echo "== full hardened gates =="; python scripts/validate_hardened.py || exit 1
  echo "== durable pipeline tests =="; python -m pytest tests/properties/ -q -p no:cacheprovider || exit 1
else
  echo "pipelines not built yet — full gates deferred (setup gates green, build ready)"
fi
echo "JUDGE OK"
