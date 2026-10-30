"""Conversion d'un énoncé LaTeX en HTML : le texte est converti, les formules
sont laissées entre délimiteurs \\( \\) et \\[ \\] pour MathJax."""
import html
import re

from .latex import read_group, skip_ws

DISPLAY_ENVS = {
    "equation": None, "equation*": None, "displaymath": None,
    "align": "aligned", "align*": "aligned", "eqnarray": "aligned", "eqnarray*": "aligned",
    "gather": "gathered", "gather*": "gathered", "multline": "gathered", "multline*": "gathered",
    "flalign": "aligned", "flalign*": "aligned", "alignat": "aligned", "alignat*": "aligned",
}
ACCENTS = {
    ("'", "e"): "é", ("`", "e"): "è", ("^", "e"): "ê", ('"', "e"): "ë", ("'", "a"): "á",
    ("`", "a"): "à", ("^", "a"): "â", ('"', "a"): "ä", ('"', "o"): "ö", ('"', "u"): "ü",
    ("'", "o"): "ó", ("^", "o"): "ô", ("'", "i"): "í", ("^", "i"): "î", ("c", "c"): "ç",
    ("'", "E"): "É", ('"', "O"): "Ö", ('"', "U"): "Ü", ("'", "u"): "ú", ("~", "n"): "ñ",
    ("v", "s"): "š", ("v", "c"): "č", ("v", "z"): "ž", ("'", "c"): "ć", ("H", "o"): "ő",
}
DROP_WITH_ARG = {"label", "footnote", "index", "vspace", "hspace", "vspace*", "hspace*",
                 "marginpar", "thanks", "phantom", "todo", "color"}
REF_CMDS = {"ref", "eqref", "cref", "Cref", "autoref", "Autoref", "pageref"}
CITE_CMDS = {"cite", "citep", "citet", "cites", "citealp", "Cite", "parencite", "textcite"}
CMD_RE = re.compile(r"\\([a-zA-Z]+\*?|.)")
OLD_STYLE_RE = re.compile(r"\{\\(em|it|itshape|sl|bf|bfseries)(?![a-zA-Z])\s*")


def expand_macros(tex, macros, depth=0):
    """Développe les macros définies par l'auteur (\\newcommand, \\def)."""
    if not macros or depth > 5:
        return tex
    names = sorted(macros, key=len, reverse=True)
    pat = re.compile("(%s)(?![a-zA-Z])" % "|".join(re.escape(n) for n in names))
    out, pos, changed = [], 0, False
    for m in pat.finditer(tex):
        if m.start() < pos:
            continue
        body = macros[m.group(1)]
        nargs = max((int(d) for d in re.findall(r"#(\d)", body)), default=0)
        i, args = m.end(), []
        for _ in range(nargs):
            i = skip_ws(tex, i)
            if i < len(tex) and tex[i] == "{":
                a, i = read_group(tex, i)
            elif i < len(tex):
                a, i = tex[i], i + 1
            else:
                a = ""
            args.append(a)
        for k, a in enumerate(args, 1):
            body = body.replace(f"#{k}", a)
        before = tex[pos:m.start()]
        out.append(before)
        # « \subset\X » ne doit pas devenir « \subsetX »
        if re.search(r"\\[a-zA-Z]+$", before) and body[:1].isalpha():
            out.append(" ")
        out.append(body if nargs or not body[-1:].isalpha() else body + " ")
        pos, changed = i, True
    out.append(tex[pos:])
    result = "".join(out)
    return expand_macros(result, macros, depth + 1) if changed else result


def split_math(tex):
    """Découpe en segments ('text', s) / ('math', s, display)."""
    segs, buf, i = [], [], 0
    begin_re = re.compile(r"\\begin\{(%s)\}" % "|".join(re.escape(e) for e in DISPLAY_ENVS))

    def flush():
        if buf:
            segs.append(("text", "".join(buf)))
            buf.clear()

    while i < len(tex):
        if tex.startswith("$$", i):
            j = tex.find("$$", i + 2)
            j = len(tex) if j < 0 else j
            flush(); segs.append(("math", tex[i + 2:j], True)); i = j + 2
        elif tex[i] == "$" and (i == 0 or tex[i - 1] != "\\"):
            j = i + 1
            while j < len(tex) and not (tex[j] == "$" and tex[j - 1] != "\\"):
                j += 1
            flush(); segs.append(("math", tex[i + 1:j], False)); i = j + 1
        elif tex.startswith("\\[", i) or tex.startswith("\\(", i):
            close = "\\]" if tex[i + 1] == "[" else "\\)"
            j = tex.find(close, i + 2)
            j = len(tex) if j < 0 else j
            flush(); segs.append(("math", tex[i + 2:j], close == "\\]")); i = j + 2
        elif tex.startswith("\\begin{", i) and (m := begin_re.match(tex, i)):
            env = m.group(1)
            end_tag = "\\end{%s}" % env
            j = tex.find(end_tag, m.end())
            j = len(tex) if j < 0 else j
            body = tex[m.end():j]
            if env.startswith("alignat"):
                body = re.sub(r"^\s*\{\d+\}", "", body)
            wrap = DISPLAY_ENVS[env]
            if wrap:
                body = "\\begin{%s}%s\\end{%s}" % (wrap, body, wrap)
            flush(); segs.append(("math", body, True)); i = j + len(end_tag)
        else:
            buf.append(tex[i]); i += 1
    flush()
    return segs


def clean_math(m):
    m = re.sub(r"\\(label|tag)\s*\{[^}]*\}", "", m)
    m = re.sub(r"\\(nonumber|notag)\b", "", m)
    return m.strip()


def text_to_html(t):
    """Convertit le texte LaTeX (hors formules) en HTML sûr."""
    out, i = [], 0
    while i < len(t):
        c = t[i]
        if c == "\\":
            m = CMD_RE.match(t, i)
            if not m:  # antislash final isolé
                i += 1
                continue
            name, i = m.group(1), m.end()
            if name in ("\\", "newline", "par"):
                out.append("<br>")
            elif name in ("%", "&", "#", "_", "$", "{", "}"):
                out.append(html.escape(name))
            elif name in (",", ";", " ", "quad", "qquad", "noindent", "medskip", "smallskip",
                          "bigskip", "item"):
                out.append(" " if name != "item" else "</li><li>")
            elif name in ("'", "`", "^", '"', "~", "c", "v", "H") and i < len(t):
                j = skip_ws(t, i)
                letter, i = (read_group(t, j) if t[j:j + 1] == "{" else (t[j:j + 1], j + 1))
                out.append(ACCENTS.get((name, letter), letter))
            elif name in ("emph", "textit", "textsl", "em", "it"):
                j = skip_ws(t, i)
                if t[j:j + 1] == "{":
                    g, i = read_group(t, j)
                    out.append(f"<em>{text_to_html(g)}</em>")
            elif name in ("textbf", "bf"):
                j = skip_ws(t, i)
                if t[j:j + 1] == "{":
                    g, i = read_group(t, j)
                    out.append(f"<strong>{text_to_html(g)}</strong>")
            elif name in CITE_CMDS or name in REF_CMDS:
                j = skip_ws(t, i)
                while t[j:j + 1] == "[":
                    j = skip_ws(t, t.find("]", j) + 1)
                if t[j:j + 1] == "{":
                    _, i = read_group(t, j)
                out.append('<span class="ref">[réf.]</span>' if name in CITE_CMDS
                           else '<span class="ref">(réf.)</span>')
            elif name in DROP_WITH_ARG:
                j = skip_ws(t, i)
                if t[j:j + 1] == "{":
                    _, i = read_group(t, j)
            elif name in ("begin", "end"):
                j = skip_ws(t, i)
                env = ""
                if t[j:j + 1] == "{":
                    env, i = read_group(t, j)
                tag = {"itemize": "ul", "enumerate": "ol", "description": "ul"}.get(env)
                if tag:
                    out.append(f"<{tag}><li>" if name == "begin" else f"</li></{tag}>")
            elif name in ("url", "href"):
                j = skip_ws(t, i)
                if t[j:j + 1] == "{":
                    g, i = read_group(t, j)
                    out.append(html.escape(g))
                    if name == "href":
                        j = skip_ws(t, i)
                        if t[j:j + 1] == "{":
                            g2, i = read_group(t, j)
                            out[-1] = text_to_html(g2)
            # commande inconnue : on la supprime, son argument éventuel reste comme texte
        elif c == "{" and (m := OLD_STYLE_RE.match(t, i)):
            g, i = read_group(t, i)
            tag = "strong" if m.group(1).startswith("bf") else "em"
            out.append(f"<{tag}>{text_to_html(g[m.end() - m.start() - 1:])}</{tag}>")
        elif c in "{}":
            i += 1
        elif c == "~":
            out.append("&nbsp;"); i += 1
        elif t.startswith("``", i) or t.startswith("''", i):
            out.append("“" if t[i] == "`" else "”"); i += 2
        elif t.startswith("---", i):
            out.append("—"); i += 3
        elif t.startswith("--", i):
            out.append("–"); i += 2
        else:
            out.append(html.escape(c)); i += 1
    s = "".join(out)
    s = re.sub(r"<(ul|ol)><li>\s*</li><li>", r"<\1><li>", s)  # premier \item
    return s


DIAGRAM_ENVS = "tikzcd|tikzpicture|figure|figure\\*|picture|xy|pspicture|tabular|table"
DIAG = "\x00DIAG\x00"


def strip_diagrams(tex):
    """Les diagrammes (TikZ, xymatrix, figures) ne sont pas rendus par MathJax :
    on les remplace par un renvoi vers l'article."""
    env = r"\\begin\{(%s)\}.*?\\end\{\1\}" % DIAGRAM_ENVS
    tex = re.sub(r"(?:\\\[|\$\$|\\begin\{(?:equation|displaymath)\*?\})\s*(?:%s)\s*"
                 r"(?:\\\]|\$\$|\\end\{(?:equation|displaymath)\*?\})" % env, DIAG, tex, flags=re.S)
    tex = re.sub(env, DIAG, tex, flags=re.S)
    while (m := re.search(r"\\xymatrix\s*(?:@[^{]*)?(?=\{)", tex)):
        _, end = read_group(tex, m.end())
        tex = tex[:m.start()] + DIAG + tex[end:]
    return tex


def latex_to_html(tex, macros=None):
    tex = strip_diagrams(expand_macros(tex, macros or {}))
    parts = []
    for seg in split_math(tex):
        if seg[0] == "text":
            parts.append(text_to_html(seg[1]))
        else:
            m = html.escape(clean_math(seg[1]))
            parts.append(f"\\[{m}\\]" if seg[2] else f"\\({m}\\)")
    s = "".join(parts)
    s = re.sub(r"\\[(\[]\s*%s\s*\\[)\]]" % DIAG, DIAG, s)
    s = s.replace(DIAG, '<span class="diag">[diagramme : voir l’article]</span>')
    s = re.sub(r"(\s*<br>\s*){2,}", "<br>", s)
    s = re.sub(r"[ \t]*\n[ \t]*\n\s*", '</div><div class="para">', s.strip())
    return f'<div class="para">{s}</div>'


def plain_text(tex):
    """Texte sans formules ni commandes, pour la recherche de concepts."""
    parts = [seg[1] for seg in split_math(tex) if seg[0] == "text"]
    t = " ".join(parts)
    t = re.sub(r"\\[a-zA-Z]+\*?", " ", t)
    t = re.sub(r"[{}~\\]", " ", t)
    return " ".join(t.split())
