#!/usr/bin/env bash
# Enchaîne toute la chaîne pour un mois donné : ./run_all.sh 2026-09 [nb_max_sources]
set -euo pipefail
MONTH="${1:?usage: ./run_all.sh AAAA-MM [nb_max_sources]}"
MAX="${2:-500}"
cd "$(dirname "$0")"
if curl -sf -o /dev/null "https://oaipmh.arxiv.org/oai?verb=Identify"; then
  python3 -m wiki.harvest --month "$MONTH"
else
  echo "export.arxiv.org inaccessible : collecte via les pages arxiv.org"
  python3 -m wiki.harvest --source web --month "$MONTH"
fi
python3 -m wiki.fetch_sources --max "$MAX"
python3 -m wiki.extract
python3 -m wiki.concepts
python3 -m wiki.build_site
