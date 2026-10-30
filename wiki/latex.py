"""Outils d'analyse LaTeX légers : commentaires, groupes, macros, environnements."""
import re
from pathlib import Path

INPUT_RE = re.compile(r"\\(?:input|include)\s*(?:\{([^}]+)\}|([A-Za-z0-9_./\-]+))")
NEWTHEOREM_RE = re.compile(r"\\newtheorem(\*?)\s*\{([^}]+)\}\s*(?:\[[^\]]*\]\s*)?\{([^}]+)\}")
THEOREMSTYLE_TITLES = {
    "definition": ("definition", "définition", "definicion", "definizione", "defn"),
    "theorem": ("theorem", "théorème", "theoreme", "satz", "teorema"),
    "proposition": ("proposition", "prop"),
    "lemma": ("lemma", "lemme", "lema"),
    "corollary": ("corollary", "corollaire", "corolario", "korollar"),
    "conjecture": ("conjecture", "conjetura", "vermutung"),
    "example": ("example", "exemple", "ejemplo", "beispiel"),
    "remark": ("remark", "remarque", "note"),
}
DEFAULT_ENVS = {
    "definition": "definition", "defn": "definition", "defi": "definition", "dfn": "definition",
    "theorem": "theorem", "thm": "theorem", "theo": "theorem", "maintheorem": "theorem",
    "proposition": "proposition", "prop": "proposition",
    "lemma": "lemma", "lem": "lemma", "corollary": "corollary", "cor": "corollary",
    "conjecture": "conjecture", "conj": "conjecture",
    "example": "example", "ex": "example", "remark": "remark", "rem": "remark",
}


def strip_comments(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def read_group(s, i):
    """s[i] == '{' : renvoie (contenu, index après l'accolade fermante)."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def skip_ws(s, i):
    while i < len(s) and s[i].isspace():
        i += 1
    return i


def preamble_files(directory: Path):
    """Tous les .sty et .tex du projet : les macros sont souvent dans un fichier à part,
    inclus de façon que load_project ne résout pas toujours."""
    files = sorted(directory.rglob("*.sty")) + sorted(directory.rglob("*.tex"))
    return "\n".join(strip_comments(p.read_text(errors="replace")) for p in files)


def load_project(directory: Path):
    """Concatène le document principal en résolvant \\input/\\include."""
    texs = sorted(directory.rglob("*.tex")) + sorted(directory.rglob("*.ltx"))
    if not texs:
        return ""
    contents = {p: p.read_text(errors="replace") for p in texs}
    main = next((p for p, t in contents.items() if "\\documentclass" in t), texs[0])
    root = directory.resolve()

    def expand(path, depth=0):
        text = strip_comments(contents.get(path) or "")
        if depth > 8:
            return text

        def repl(m):
            name = (m.group(1) or m.group(2)).strip()
            for cand in (path.parent / name, path.parent / f"{name}.tex",
                         directory / name, directory / f"{name}.tex"):
                cand = cand.resolve()
                if cand.is_relative_to(root) and cand in {p.resolve() for p in contents}:
                    real = next(p for p in contents if p.resolve() == cand)
                    return expand(real, depth + 1)
            return ""
        return INPUT_RE.sub(repl, text)

    return expand(main)


def theorem_envs(tex):
    """Associe les noms d'environnements déclarés à un type canonique."""
    envs = dict(DEFAULT_ENVS)
    for m in NEWTHEOREM_RE.finditer(tex):
        name, title = m.group(2).strip(), m.group(3).strip().lower()
        title = re.sub(r"\\[a-zA-Z]+\s*", "", title)
        for kind, words in THEOREMSTYLE_TITLES.items():
            if any(title.startswith(w) for w in words):
                envs[name] = kind
                break
    return envs


def macros(tex):
    """Macros simples utilisables par KaTeX : {'\\R': '\\mathbb{R}', ...}."""
    out = {}
    for m in re.finditer(r"\\(?:(?:re)?newcommand|providecommand|DeclareRobustCommand)\*?\s*\{?\s*(\\[a-zA-Z]+)\s*\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*(?=\{)", tex):
        body, _ = read_group(tex, m.end())
        out[m.group(1)] = body.strip()
    for m in re.finditer(r"\\def\s*(\\[a-zA-Z]+)\s*(?:#\d)*\s*(?=\{)", tex):
        body, _ = read_group(tex, m.end())
        out.setdefault(m.group(1), body.strip())
    for m in re.finditer(r"\\DeclareMathOperator\*?\s*\{?\s*(\\[a-zA-Z]+)\s*\}?\s*(?=\{)", tex):
        body, _ = read_group(tex, m.end())
        out[m.group(1)] = "\\operatorname{%s}" % body.strip()
    # on écarte ce que KaTeX ne saura pas exploiter
    return {k: v for k, v in out.items()
            if len(v) < 300 and "\\begin" not in v and "@" not in v
            and not re.search(r"\\par(?![a-zA-Z])", v)}


def environments(tex, envs):
    """Renvoie [(kind, env, titre_optionnel, corps)] dans l'ordre du document."""
    out = []
    begin_re = re.compile(r"\\begin\{(%s)\}" % "|".join(re.escape(e) for e in envs))
    pos = 0
    while True:
        m = begin_re.search(tex, pos)
        if not m:
            break
        env = m.group(1)
        i = skip_ws(tex, m.end())
        title = ""
        if i < len(tex) and tex[i] == "[":
            j = tex.find("]", i)
            title, i = tex[i + 1:j].strip(), j + 1
        # fin correspondante (gère l'imbrication du même environnement)
        tag_re = re.compile(r"\\(begin|end)\{%s\}" % re.escape(env))
        depth, k, end = 1, i, None
        for t in tag_re.finditer(tex, i):
            depth += 1 if t.group(1) == "begin" else -1
            if depth == 0:
                end, k = t.start(), t.end()
                break
        if end is None:
            break
        out.append((envs[env], env, title, tex[i:end].strip()))
        pos = k
    return out


EMPH_RE = re.compile(r"\\(?:emph|textit|textbf|textsl|defn|dfn|term|emph\*)\s*(?=\{)")
OLD_EMPH_RE = re.compile(r"\{\\(?:em|it|bf|bfseries|itshape)\s+")


def defined_terms(body):
    """Termes mis en évidence dans une définition (\\emph{...}, {\\em ...}, ...)."""
    terms = []
    for m in EMPH_RE.finditer(body):
        g, _ = read_group(body, m.end())
        terms.append(g)
    for m in OLD_EMPH_RE.finditer(body):
        g, _ = read_group(body, m.start())
        terms.append(OLD_EMPH_RE.sub("", "{" + g)[0:])
    return terms
