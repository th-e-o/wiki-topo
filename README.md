# Wiki Topologie

Prototype de wiki de topologie construit automatiquement à partir d'arXiv
(catégories `math.GN`, `math.AT`, `math.GT`, y compris les listages croisés).

## Ce que fait la chaîne

| Étape | Module | Sortie |
|---|---|---|
| 1. Métadonnées (titre, auteurs, résumé, catégories, **licence**) | `wiki/harvest.py` | `data/papers.jsonl` |
| 2. Sources LaTeX (e-print) | `wiki/fetch_sources.py` | `data/src/<id>/` |
| 3. Extraction des définitions, théorèmes, conjectures… | `wiki/extract.py` | `data/statements.jsonl` |
| 4. Index des concepts (glossaire + termes définis) | `wiki/concepts.py` | `data/concepts.json` |
| 5. Site statique (une page, recherche, MathJax) | `wiki/build_site.py` | `site/index.html` |

```bash
pip install -r requirements.txt
./run_all.sh 2026-09          # un mois de dépôts
python3 -m tests.test_pipeline
```

Pour cumuler plusieurs mois, relancez la commande avec un autre mois :
`data/papers.jsonl` est enrichi à chaque passage, puis le site est régénéré.

## Accès réseau

- **Voie recommandée** : OAI-PMH sur `oaipmh.arxiv.org` (vers lequel redirige `export.arxiv.org/oai2`) (`--source oai`), avec des pages de 1000 articles.
- **Voie de secours** : listings mensuels et pages `/abs/` sur `arxiv.org` (`--source web`), à raison d'une page par article.
- Les sources LaTeX viennent de `arxiv.org/e-print/<id>`. Pour des volumes importants
  (plus de quelques milliers d'articles), utilisez le bulk data S3 d'arXiv.
- Toutes les requêtes respectent la règle d'arXiv : au plus une requête toutes les 3 secondes.

## Licences

Les métadonnées arXiv sont en CC0. Les énoncés extraits ne sont **reproduits** que pour
les articles sous CC BY, CC BY-SA ou CC0 (`OPEN_LICENSES` dans `wiki/config.py`), avec attribution.
Pour les autres articles, le site indique seulement qu'un énoncé existe et renvoie vers arXiv.

## Limites du prototype

- Aucun texte n'est rédigé ni vérifié : il n'y a ni synthèse par LLM ni relecture humaine.
- Les termes contenant une formule (`$k$-connected`) sont ignorés.
- La correspondance concept ↔ article est lexicale, donc des faux positifs sont possibles sur des mots courants.
- Les macros LaTeX ne sont développées que dans les cas simples.

## Pistes

- Une synthèse rédigée par concept (LLM), sourcée et marquée « non vérifiée ».
- Le rattachement à zbMATH Open, aux classes MSC et aux identifiants Wikidata.
- Une version éditable (MediaWiki) alimentée par ces données.
