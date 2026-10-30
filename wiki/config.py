"""Paramètres du pipeline wiki-topologie."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"          # archives e-print téléchargées (non fiables)
SRC = DATA / "src"          # sources LaTeX extraites
SITE = ROOT / "site"

# Sous-catégories arXiv retenues pour la topologie
CATEGORIES = {
    "math.GN": "Topologie générale",
    "math.AT": "Topologie algébrique",
    "math.GT": "Topologie géométrique",
}

# OAI-PMH : métadonnées arXiv (CC0), incluant la licence de chaque article
OAI_URL = "https://oaipmh.arxiv.org/oai"  # export.arxiv.org/oai2 redirige ici
OAI_SET = "math:math"
EPRINT_URL = "https://arxiv.org/e-print/{id}"
USER_AGENT = "wiki-topologie/0.1 (prototype; contact: voir README)"
DELAY_SECONDS = 3.0         # règle d'arXiv : au plus 1 requête / 3 s

# Licences dont on peut reproduire des extraits (énoncés) avec attribution.
# Les autres articles ne sont que cités et liés.
OPEN_LICENSES = (
    "creativecommons.org/licenses/by/",
    "creativecommons.org/licenses/by-sa/",
    "creativecommons.org/publicdomain/zero/",
)

ENVIRONMENTS = {
    "definition": "Définition",
    "theorem": "Théorème",
    "proposition": "Proposition",
    "lemma": "Lemme",
    "corollary": "Corollaire",
    "conjecture": "Conjecture",
    "example": "Exemple",
    "remark": "Remarque",
}

MIN_PAPERS_PER_CONCEPT = 2  # un terme défini doit apparaître dans ≥ 2 articles
MAX_STATEMENT_CHARS = 2500
