(function () {
  "use strict";
  var W = window.WIKI;
  var H = window.WIKI_H || {};
  Object.keys(H).forEach(function (i) { W.statements[i].h = H[i]; });
  var view = document.getElementById("view");
  var q = document.getElementById("q");
  var bySlug = {};
  W.concepts.forEach(function (c) { bySlug[c.s] = c; });
  var byAnchor = {};
  Object.keys(W.papers).forEach(function (id) { W.papers[id].id = id; byAnchor[W.papers[id].a] = W.papers[id]; });
  var conceptsOfPaper = {};
  W.concepts.forEach(function (c) {
    c.p.forEach(function (id) { (conceptsOfPaper[id] = conceptsOfPaper[id] || []).push(c); });
  });

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch];
    });
  }
  function periodText() {
    return W.period[0] === W.period[1] ? "en " + W.period[0] : "de " + W.period[0] + " à " + W.period[1];
  }
  function name(c) { return c.fr || cap(c.en); }
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function plural(n, one, many) { return n + " " + (n > 1 ? many : one); }
  function authors(p, max) {
    max = max || 3;
    if (!p.au.length) return "";
    return p.au.length > max ? p.au.slice(0, max).join(", ") + " et al." : p.au.join(", ");
  }
  function arxivUrl(p, kind) { return "https://arxiv.org/" + (kind || "abs") + "/" + p.id; }
  function cleanTitle(html) { var d = document.createElement("div"); d.innerHTML = html; return d.textContent; }

  function licTag(p) {
    return '<a class="lic' + (p.open ? " open" : "") + '" href="' + esc(p.licUrl) +
      '" target="_blank" rel="noopener">' + esc(p.lic) + "</a>";
  }

  function stmt(i) {
    var s = W.statements[i], p = W.papers[s.p];
    var head = '<span class="k">' + esc(W.kinds[s.k] || s.k) + "</span>" + (s.t ? " (" + s.t + ")" : "") + ".";
    return '<article class="stmt" data-k="' + s.k + '">' +
      '<div class="stmt-head">' + head + "</div>" +
      '<div class="stmt-body">' + s.h + (s.tr ? '<div class="para ref">[…] énoncé tronqué</div>' : "") + "</div>" +
      '<div class="stmt-src">Extrait de <a href="#' + p.a + '"><span class="id">arXiv:' + p.id + "</span></a> · " +
      authors(p, 2) + " · " + licTag(p) + "</div></article>";
  }

  function paperItem(p) {
    return '<li><a class="ptitle" href="#' + p.a + '">' + p.t + "</a>" +
      '<div class="pmeta">' + authors(p) + ' · <span class="id">' + p.id + "</span> · " + p.d +
      " · " + p.c.filter(function (c) { return W.branches[c]; }).join(", ") + " · " + licTag(p) + "</div></li>";
  }

  function chips(list) {
    return '<ul class="chips">' + list.map(function (c) {
      return '<li><a href="#concept-' + c.s + '">' + name(c) + "</a></li>";
    }).join("") + "</ul>";
  }

  function splitOpen(idx) {
    var open = [], closed = [];
    idx.forEach(function (i) { (W.statements[i].h ? open : closed).push(i); });
    return { open: open, closed: closed };
  }
  function closedNote(idx, what) {
    if (!idx.length) return "";
    var ids = [];
    idx.forEach(function (i) { var p = W.statements[i].p; if (ids.indexOf(p) < 0) ids.push(p); });
    return '<p class="note">' + plural(idx.length, what, what + "s") + " dans " +
      plural(ids.length, "article", "articles") + " dont la licence ne permet pas de reproduire le texte : " +
      ids.map(function (id) {
        return '<a href="' + arxivUrl(W.papers[id]) + '" target="_blank" rel="noopener" class="id">arXiv:' + id + "</a>";
      }).join(", ") + ".</p>";
  }

  /* ---------- vues ---------- */

  function home() {
    var nOpen = Object.keys(W.papers).filter(function (id) { return W.papers[id].open; }).length;
    var nDef = W.statements.filter(function (s) { return s.k === "definition"; }).length;
    var cols = Object.keys(W.branches).map(function (b) {
      var list = W.concepts.filter(function (c) { return c.b === b; })
        .sort(function (x, y) { return y.p.length - x.p.length; });
      return '<section class="branch"><h2>' + esc(W.branches[b]) + ' <span class="code">' + b + "</span></h2>" +
        (list.length ? '<ul class="clist">' + list.map(function (c) {
          return '<li><a href="#concept-' + c.s + '"><span class="cname">' + name(c) +
            (c.fr ? "<small>" + c.en + "</small>" : "") + '</span><span class="count">' +
            plural(c.p.length, "article", "articles") + "</span></a></li>";
        }).join("") + "</ul>" : '<p class="empty">Aucun concept pour cette période.</p>') + "</section>";
    }).join("");
    return '<div class="wrap"><div class="read"><p class="eyebrow">arXiv · ' + Object.keys(W.branches).join(" · ") +
      "</p><h1>Les concepts de la topologie, d’après les prépublications arXiv</h1>" +
      '<p class="lede">Chaque page réunit les articles récents qui emploient un concept, les définitions et ' +
      "énoncés extraits de leurs sources LaTeX quand la licence le permet, et les concepts voisins.</p>" +
      '<div class="stats"><span><b>' + W.concepts.length + "</b> concepts</span><span><b>" +
      Object.keys(W.papers).length + "</b> articles</span><span><b>" + nOpen + "</b> sous licence ouverte</span><span><b>" +
      nDef + "</b> définitions extraites</span><span>" + periodText() + "</span></div></div>" +
      '<div class="branches">' + cols + "</div></div>";
  }

  function conceptView(c) {
    var defs = splitOpen(c.df), sts = splitOpen(c.st);
    var rel = c.rel.map(function (s) { return bySlug[s]; }).filter(Boolean);
    var papers = c.p.map(function (id) { return W.papers[id]; });
    return '<div class="wrap"><div class="read">' +
      '<p class="eyebrow">' + esc(W.branches[c.b] || c.b) + " · " + (c.src === "glossaire" ? "glossaire" : "terme défini dans les articles") + "</p>" +
      "<h1>" + name(c) + "</h1>" +
      (c.fr ? '<p class="lede"><span class="id">' + c.en + "</span>" + (c.al.length ? " · aussi : " + c.al.join(", ") : "") + "</p>" :
        (c.al.length ? '<p class="lede">Aussi : ' + c.al.join(", ") + "</p>" : "")) +
      '<div class="stats"><span><b>' + c.p.length + "</b> " + (c.p.length > 1 ? "articles" : "article") +
      "</span><span><b>" + c.df.length + "</b> " + (c.df.length > 1 ? "définitions" : "définition") +
      "</span><span><b>" + c.st.length + "</b> " + (c.st.length > 1 ? "énoncés liés" : "énoncé lié") + "</span></div></div>" +

      '<section class="section read"><h2>Définitions</h2>' +
      (defs.open.length ? '<div class="stack">' + defs.open.map(stmt).join("") + "</div>" : "") +
      closedNote(defs.closed, "définition") +
      (!c.df.length ? '<p class="empty">Aucune définition extraite pour l’instant. Les articles ci-dessous emploient ce terme dans leur titre ou leur résumé.</p>' : "") +
      "</section>" +

      (c.st.length ? '<section class="section read"><h2>Énoncés qui l’emploient</h2>' +
        (sts.open.length ? '<div class="stack">' + sts.open.slice(0, 12).map(stmt).join("") + "</div>" : "") +
        (sts.open.length > 12 ? '<p class="note">' + (sts.open.length - 12) + " autres énoncés dans les articles listés plus bas.</p>" : "") +
        closedNote(sts.closed, "énoncé") + "</section>" : "") +

      (rel.length ? '<section class="section read"><h2>Concepts liés</h2>' + chips(rel) +
        '<p class="note">Concepts qui apparaissent souvent dans les mêmes articles.</p></section>' : "") +

      '<section class="section read"><h2>Articles <span class="count">' + papers.length + "</span></h2>" +
      '<ul class="plist">' + papers.map(paperItem).join("") + "</ul></section></div>";
  }

  function paperView(p) {
    var sts = splitOpen(p.sts);
    var cs = (conceptsOfPaper[p.id] || []).slice().sort(function (a, b) { return name(a).localeCompare(name(b), "fr"); });
    return '<div class="wrap"><div class="read">' +
      '<p class="eyebrow"><span class="id">arXiv:' + p.id + "</span> · " + p.d + " · " + p.c.join(", ") + "</p>" +
      "<h1>" + p.t + "</h1>" +
      '<p class="lede">' + p.au.join(", ") + "</p>" +
      '<div class="stats"><span><a href="' + arxivUrl(p) + '" target="_blank" rel="noopener">Page arXiv</a></span>' +
      '<span><a href="' + arxivUrl(p, "pdf") + '" target="_blank" rel="noopener">PDF</a></span>' +
      "<span>" + licTag(p) + "</span>" + (p.msc ? "<span>MSC " + p.msc + "</span>" : "") + "</div></div>" +
      '<section class="section read"><h2>Résumé</h2><div class="abstract prose"><p>' + p.abs + "</p></div></section>" +
      (cs.length ? '<section class="section read"><h2>Concepts</h2>' + chips(cs) + "</section>" : "") +
      '<section class="section read"><h2>Énoncés extraits <span class="count">' + p.sts.length + "</span></h2>" +
      (sts.open.length ? '<div class="stack">' + sts.open.map(stmt).join("") + "</div>" :
        p.sts.length ? '<p class="note">' + plural(p.sts.length, "énoncé extrait", "énoncés extraits") +
          ", non reproduits : la licence de l’article (" + esc(p.lic) + ") ne le permet pas. Ils servent uniquement à relier l’article aux concepts.</p>" :
        '<p class="empty">Aucun énoncé extrait : la source LaTeX n’a pas encore été analysée.</p>') +
      "</section></div>";
  }

  var filt = { branch: "", open: false };
  function articlesView() {
    var list = Object.keys(W.papers).map(function (id) { return W.papers[id]; })
      .filter(function (p) { return (!filt.branch || p.c.indexOf(filt.branch) >= 0) && (!filt.open || p.open); })
      .sort(function (a, b) { return a.d < b.d ? 1 : a.d > b.d ? -1 : 0; });
    var btn = function (key, val, label, pressed) {
      return '<button type="button" data-f="' + key + '" data-v="' + val + '" aria-pressed="' + pressed + '">' + label + "</button>";
    };
    return '<div class="wrap"><div class="read"><p class="eyebrow">Corpus</p><h1>Articles</h1>' +
      '<p class="lede">' + plural(list.length, "article", "articles") + ", du plus récent au plus ancien.</p></div>" +
      '<div class="filters">' + btn("branch", "", "Toutes les branches", !filt.branch) +
      Object.keys(W.branches).map(function (b) { return btn("branch", b, esc(W.branches[b]), filt.branch === b); }).join("") +
      btn("open", "1", "Licence ouverte uniquement", filt.open) + "</div>" +
      '<ul class="plist read">' + list.map(paperItem).join("") + "</ul></div>";
  }

  function methodView() {
    return '<div class="wrap"><div class="read prose"><p class="eyebrow">À propos</p><h1>Méthode</h1>' +
      '<p class="lede">Ce wiki est produit automatiquement à partir d’arXiv. Aucun texte n’a été rédigé ni vérifié par un humain : ' +
      "chaque énoncé renvoie à sa source, qu’il faut consulter avant toute citation.</p>" +
      "<h2>Corpus</h2><p>Articles déposés " + periodText() + " dans les catégories " +
      Object.keys(W.branches).map(function (b) { return esc(W.branches[b]) + " (" + b + ")"; }).join(", ") +
      ", y compris les articles listés en catégorie secondaire. " + W.withSource + " sources LaTeX ont été analysées.</p>" +
      "<h2>Étapes</h2><ul><li>Métadonnées (titre, auteurs, résumé, catégories, licence) lues sur arXiv. Elles sont publiées sous CC0.</li>" +
      "<li>Sources LaTeX téléchargées, puis analyse des environnements déclarés par <span class=\"id\">\\newtheorem</span> : définitions, théorèmes, propositions, lemmes, corollaires, conjectures.</li>" +
      "<li>Les termes mis en évidence dans une définition (<span class=\"id\">\\emph</span>, <span class=\"id\">\\textbf</span>…) deviennent des concepts candidats. Ils s’ajoutent à un glossaire de départ d’environ 90 notions avec leur nom français.</li>" +
      "<li>Un article est rattaché à un concept quand le terme figure dans son titre, son résumé ou ses énoncés. Les concepts liés sont ceux qui partagent le plus d’articles.</li></ul>" +
      "<h2>Licences</h2><p>Les énoncés ne sont reproduits que pour les articles sous CC BY, CC BY-SA ou CC0, avec attribution. " +
      "Pour les autres articles (licence arXiv par défaut, CC BY-NC…), le wiki indique seulement qu’un énoncé existe et renvoie vers arXiv.</p>" +
      "<h2>Limites connues</h2><ul><li>Les macros LaTeX propres à chaque auteur sont développées quand elles sont simples. Certaines formules peuvent mal s’afficher.</li>" +
      "<li>Les termes contenant une formule (par exemple « $k$-connected ») sont écartés.</li>" +
      "<li>La détection des concepts repose sur la correspondance de mots. Un terme courant comme « link » peut être rattaché à un article à tort.</li></ul></div></div>";
  }

  function searchView(term) {
    var t = term.toLowerCase();
    var cs = W.concepts.filter(function (c) {
      return (c.fr + " " + c.en + " " + c.al.join(" ")).toLowerCase().indexOf(t) >= 0;
    });
    var ps = Object.keys(W.papers).map(function (id) { return W.papers[id]; }).filter(function (p) {
      return (cleanTitle(p.t) + " " + p.au.join(" ") + " " + p.id).toLowerCase().indexOf(t) >= 0;
    }).slice(0, 60);
    return '<div class="wrap"><div class="read"><p class="eyebrow">Recherche</p><h1>« ' + esc(term) + " »</h1></div>" +
      '<section class="section read"><h2>Concepts <span class="count">' + cs.length + "</span></h2>" +
      (cs.length ? chips(cs) : '<p class="empty">Aucun concept ne correspond. Essayez le terme anglais, par exemple « knot » ou « homotopy ».</p>') + "</section>" +
      '<section class="section read"><h2>Articles <span class="count">' + ps.length + "</span></h2>" +
      (ps.length ? '<ul class="plist">' + ps.map(paperItem).join("") + "</ul>" : '<p class="empty">Aucun article ne correspond.</p>') +
      "</section></div>";
  }

  /* ---------- routage ---------- */

  function typeset() {
    if (!window.MathJax || !MathJax.startup || !MathJax.startup.promise) return;
    MathJax.startup.promise.then(function () {
      if (MathJax.typesetClear) MathJax.typesetClear();
      return MathJax.typesetPromise([view]);
    }).catch(function (e) { console.warn("MathJax", e); });
  }

  function render(fromSearch) {
    var h = decodeURIComponent(location.hash.slice(1));
    var term = q.value.trim();
    var nav = "accueil", html;
    if (term.length >= 2) {
      html = searchView(term); nav = "";
    } else if (h.indexOf("concept-") === 0 && bySlug[h.slice(8)]) {
      html = conceptView(bySlug[h.slice(8)]);
    } else if (h.indexOf("article-") === 0 && byAnchor[h]) {
      html = paperView(byAnchor[h]); nav = "articles";
    } else if (h === "articles") {
      html = articlesView(); nav = "articles";
    } else if (h === "methode") {
      html = methodView(); nav = "methode";
    } else {
      html = home();
    }
    view.innerHTML = html;
    document.querySelectorAll(".nav a").forEach(function (a) {
      if (a.getAttribute("href") === "#" + nav) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    var c = h.indexOf("concept-") === 0 && bySlug[h.slice(8)];
    document.title = (c && !term ? name(c) + " · " : "") + "Wiki Topologie";
    if (!fromSearch) { window.scrollTo(0, 0); }
    typeset();
  }

  view.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-f]");
    if (!b) return;
    if (b.dataset.f === "branch") filt.branch = b.dataset.v;
    else filt.open = !filt.open;
    render(true);
  });
  window.addEventListener("hashchange", function () { q.value = ""; render(false); });
  var timer;
  q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { render(true); }, 150); });

  document.getElementById("foot").innerHTML =
    "Métadonnées et sources : arXiv (métadonnées sous CC0). Thank you to arXiv for use of its open access interoperability. " +
    "Énoncés reproduits uniquement pour les articles sous licence CC BY, CC BY-SA ou CC0. Généré le " + W.built + ".";
  render(false);
})();
