"""Construction de l'index des concepts à partir du glossaire et des définitions extraites.

Usage : python -m wiki.concepts
Sortie : data/concepts.json
"""
import json
import re
from collections import Counter, defaultdict

from . import config
from .glossary import GLOSSARY
from .render import plain_text

# termes trop vagues pour faire une page
STOP = {"map", "set", "function", "space", "group", "graph", "point", "element", "pair",
        "sequence", "family", "collection", "subset", "condition", "property", "notion",
        "case", "type", "class", "object", "morphism", "category", "structure", "complex",
        "invariant", "number", "degree", "order", "rank", "length", "weight", "index",
        "sum", "product", "system", "operation", "action", "module", "algebra", "ring",
        "field", "vertex", "edge", "cell", "face", "path", "loop", "curve", "disk"}


VERBISH = {"to", "is", "are", "be", "if", "we", "it", "of", "on", "in", "by", "for", "with",
           "and", "or", "that", "which", "belongs", "said", "called", "has", "have",
           "not", "necessarily", "almost", "surely", "one", "i", "ii", "iii", "such", "any",
           "at", "over", "under", "from", "into", "onto", "non", "pairwise", "very", "more", "less"}
ADJ_PREFIXES = ("non-", "finite-", "well-", "strict-", "infinite-", "locally-", "weakly-")


def is_noun_phrase(t):
    """Garde les termes composés (« homotopy equivalence ») ; les mots isolés extraits
    sont surtout des adjectifs (« closed », « positive ») et font des pages vides de sens."""
    words = t.split()
    if t in STOP or len(words) < 2 and not (len(words) == 1 and t.count("-") >= 1 and not t.startswith(ADJ_PREFIXES)):
        return False
    if any(w in VERBISH for w in words) or words[-1] in STOP and len(words) == 1:
        return False
    if words[0].endswith("ly") or words[-1].endswith(("ed", "ly", "ent", "ive", "ous", "ible", "able")) \
            and not words[-1].endswith(("bed", "eed")):
        return False  # « finitely generated », « locally convex » : adjectifs, pas des notions
    if len(words) == 1 and not re.search(r"(ism|ion|ity|ology|ence|ance|ment|space|group|manifold|complex|knot|map)$", t):
        return False  # mot composé à trait d'union : seulement s'il finit comme un nom
    return True


def slugify(s):
    s = s.lower().replace("∞", "infinity")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def term_regex(term):
    words = [re.escape(w) for w in re.split(r"[\s\-]+", term) if w]
    return re.compile(r"(?<![a-z0-9])" + r"[\s\-]+".join(words) + r"(?:s|es)?(?![a-z0-9])")


def main():
    papers = {json.loads(l)["id"]: json.loads(l)
              for l in (config.DATA / "papers.jsonl").read_text().splitlines()}
    st_path = config.DATA / "statements.jsonl"
    statements = [json.loads(l) for l in st_path.read_text().splitlines()] if st_path.exists() else []

    # texte cherchable par article : titre + résumé (+ énoncés extraits)
    text = {pid: plain_text(p["title"] + " . " + p["abstract"]).lower() for pid, p in papers.items()}
    st_text = [plain_text(s["body"]).lower() for s in statements]

    # 1. candidats : glossaire, puis termes définis dans les articles
    cands = {}
    for key, (fr, branch, aliases) in GLOSSARY.items():
        cands[key] = {"key": key, "fr": fr, "branch": branch, "forms": [key] + aliases,
                      "source": "glossaire"}
    alias_of = {f: key for key, c in cands.items() for f in c["forms"]}
    defined = defaultdict(set)
    for i, s in enumerate(statements):
        for t in s["terms"]:
            defined[alias_of.get(t, t)].add(i)
    seen = {k.replace("-", " ") for k in cands}
    for t, idx in sorted(defined.items(), key=lambda kv: -len(kv[1])):
        if t in cands or not is_noun_phrase(t):
            continue
        if t.replace("-", " ") in seen:  # « weak-equivalence » = « weak equivalence »
            canon = next(k for k in cands if k.replace("-", " ") == t.replace("-", " "))
            defined[canon] |= idx
            continue
        seen.add(t.replace("-", " "))
        cands[t] = {"key": t, "fr": None, "branch": None, "forms": [t], "source": "extrait"}

    word_index = defaultdict(set)
    for i, t in enumerate(st_text):
        for w in set(re.findall(r"[a-z0-9]+", t)):
            word_index[w].add(i)

    def candidates_for(forms):
        out = set()
        for f in forms:
            first = re.findall(r"[a-z0-9]+", f)[:1]
            out |= word_index.get(first[0], set()) if first else set()
        return sorted(out)

    # 2. occurrences
    concepts = []
    for key, c in cands.items():
        regs = [term_regex(f) for f in c["forms"]]
        hit = lambda s: any(r.search(s) for r in regs)
        mention = sorted(pid for pid, t in text.items() if hit(t))
        # seuls les énoncés contenant le premier mot du terme sont testés
        st_hits = [i for i in candidates_for(c["forms"])
                   if statements[i]["kind"] not in ("definition", "remark", "example") and hit(st_text[i])]
        defs = sorted(defined.get(key, ()))
        all_papers = set(mention) | {statements[i]["paper"] for i in defs + st_hits}
        if c["source"] == "extrait" and len(all_papers) < config.MIN_PAPERS_PER_CONCEPT:
            continue
        if not all_papers:
            continue
        branch = c["branch"]
        if not branch:
            cats = Counter(cat for pid in all_papers for cat in papers[pid]["categories"]
                           if cat in config.CATEGORIES)
            branch = cats.most_common(1)[0][0] if cats else "math.GT"
        concepts.append({
            "slug": slugify(key), "key": key, "fr": c["fr"], "branch": branch,
            "source": c["source"], "aliases": c["forms"][1:],
            "papers": sorted(all_papers, key=lambda p: papers[p]["created"], reverse=True),
            "definitions": defs, "statements": st_hits[:40],
        })

    # 3. concepts liés : co-occurrence dans les mêmes articles (indice de Jaccard)
    sets = {c["slug"]: set(c["papers"]) for c in concepts}
    for c in concepts:
        a = sets[c["slug"]]
        scores = []
        for other, b in sets.items():
            if other == c["slug"]:
                continue
            inter = len(a & b)
            if inter >= 2 or (inter and min(len(a), len(b)) <= 2):
                scores.append((inter / len(a | b), other))
        c["related"] = [s for _, s in sorted(scores, reverse=True)[:8]]

    concepts.sort(key=lambda c: (c["fr"] or c["key"]).lower())
    (config.DATA / "concepts.json").write_text(json.dumps(concepts, ensure_ascii=False, indent=1))
    src = Counter(c["source"] for c in concepts)
    print(f"{len(concepts)} concepts ({src['glossaire']} du glossaire, {src['extrait']} extraits)")


if __name__ == "__main__":
    main()
