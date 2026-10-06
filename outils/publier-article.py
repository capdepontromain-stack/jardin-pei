#!/usr/bin/env python3
"""
publier-article.py : génère un article du blog Jardin Péi à partir d'un fichier .md,
régénère la liste du blog, le bloc « Derniers conseils » de l'accueil, le sitemap et le flux RSS.

Usage :
  python3 outils/publier-article.py outils/articles/mon-article.md            # génère seulement
  python3 outils/publier-article.py outils/articles/mon-article.md --publier  # + git push + Hostinger + IndexNow + vérif 200
  python3 outils/publier-article.py --regenerer [--publier]                   # régénère tout depuis outils/articles.json

Format du .md (en-tête puis corps) :
---
titre: Quand tondre sa pelouse à La Réunion
description: meta description, 158 caractères maximum
slug: quand-tondre-pelouse-la-reunion
date: 2026-10-06
image: tonte-pelouse-saint-leu.jpg        (fichier dans /photos/)
alt: Tonte de pelouse à Saint-Leu
---
Corps en Markdown simple : ## titres, ### sous-titres, paragraphes, listes « - », **gras**, [liens](url).
Une section « ## Questions fréquentes » avec des paragraphes « **Question ?** Réponse. » produit un schéma FAQPage.

Règles vérifiées avant écriture : pas de tiret cadratin, meta <= 158, titre <= 70, slug unique, pas de montant en euros.
"""
import json, re, sys, subprocess, html, datetime, pathlib, urllib.request

RACINE = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://jardinpei.re"
REG = RACINE / "outils" / "articles.json"
TEL_AFF, TEL_LIEN = "06 93 12 32 39", "+262693123239"
MAIL = "grondin.matheo416@gmail.com"

HEADER = """<header>
  <div class="wrap nav">
    <a class="brand" href="/"><img src="/logo.svg" alt="Jardin Péi, entretien de jardin à Saint-Leu" width="46" height="46"><span>Jardin <b>Péi</b></span></a>
    <nav><ul>
      <li><a href="/#services">Services</a></li>
      <li><a href="/#pourquoi">Pourquoi Mathéo</a></li>
      <li><a href="/#zone">Zone</a></li>
      <li><a href="/#tarifs">Tarifs</a></li>
      <li><a href="/#faq">Questions</a></li>
      <li><a href="/blog/">Conseils</a></li>
      <li><a href="/#contact">Contact</a></li>
    </ul></nav>
    <a class="tel-nav" href="tel:%s"><svg viewBox="0 0 24 24"><path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/></svg><span class="num">%s</span></a>
  </div>
</header>
""" % (TEL_LIEN, TEL_AFF)

FOOTER = """<footer>
  <div class="wrap">
    <div class="cols">
      <div><h3>Jardin Péi</h3><p>Entretien de jardin et d'espaces verts à domicile par Mathéo, étudiant à L'Étang Saint-Leu. Tonte, taille de haies, débroussaillage, déchets verts, petits travaux de jardinage avec un matériel léger.</p></div>
      <div><h3>Zone d'intervention</h3><ul><li>L'Étang Saint-Leu et Pointe au Sel</li><li>Saint-Leu</li><li>Piton Saint-Leu et La Chaloupe</li><li>Trois-Bassins</li><li>Quartiers voisins sur demande</li></ul></div>
      <div><h3>Contact</h3><ul><li><a href="tel:%s">%s</a></li><li><a href="https://wa.me/262693123239" target="_blank" rel="noopener">WhatsApp</a></li><li><a href="mailto:%s">%s</a></li><li><a href="/blog/">Conseils jardin (blog)</a></li><li>L'Étang Saint-Leu, 97424 Saint-Leu, La Réunion</li></ul></div>
    </div>
    <div class="bas">© Jardin Péi, Mathéo Grondin · L'Étang Saint-Leu, La Réunion · Photos de jardins : illustrations</div>
  </div>
</footer>

<div class="barre">
  <a class="a1" href="tel:%s">Appeler Mathéo</a>
  <a class="a2" href="https://wa.me/262693123239" target="_blank" rel="noopener">WhatsApp</a>
</div>
""" % (TEL_LIEN, TEL_AFF, MAIL, MAIL, TEL_LIEN)

ENCART = """<div class="encart">
  <b>Un jardin à entretenir à Saint-Leu, Piton Saint-Leu ou Trois-Bassins ?</b>
  <p>Appelez Mathéo, étudiant jardinier à L'Étang Saint-Leu. Prix annoncé avant de commencer, matériel léger, travail propre.</p>
  <a class="btn btn-plein" href="tel:%s">Appeler le %s</a>
  <a class="btn btn-ligne" href="https://wa.me/262693123239" target="_blank" rel="noopener">WhatsApp</a>
</div>
""" % (TEL_LIEN, TEL_AFF)

MOIS = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]

def date_fr(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {MOIS[d.month-1]} {d.year}"

def lire_md(chemin):
    txt = pathlib.Path(chemin).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", txt, re.S)
    if not m: sys.exit("En-tête --- manquant")
    meta = {}
    for ligne in m.group(1).splitlines():
        if ":" in ligne:
            k, v = ligne.split(":", 1); meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
    return t

def md_vers_html(corps):
    """Markdown minimal -> HTML. Retourne (html, faq[(q,r)], texte_brut)."""
    out, faq, brut = [], [], []
    en_faq, liste = False, None
    def fermer_liste():
        nonlocal liste
        if liste: out.append(f"</{liste}>"); liste = None
    for bloc in re.split(r"\n\s*\n", corps):
        bloc = bloc.strip()
        if not bloc: continue
        if bloc.startswith("### "):
            fermer_liste(); out.append(f"<h3>{inline(bloc[4:])}</h3>"); brut.append(bloc[4:]); continue
        if bloc.startswith("## "):
            fermer_liste(); titre = bloc[3:]; en_faq = "question" in titre.lower()
            out.append(f"<h2>{inline(titre)}</h2>"); brut.append(titre); continue
        if all(l.strip().startswith("- ") for l in bloc.splitlines()):
            fermer_liste(); out.append("<ul>" + "".join(f"<li>{inline(l.strip()[2:])}</li>" for l in bloc.splitlines()) + "</ul>")
            brut.extend(l.strip()[2:] for l in bloc.splitlines()); continue
        if re.match(r"^\d+\. ", bloc.splitlines()[0]):
            fermer_liste(); out.append("<ol>" + "".join(f"<li>{inline(re.sub(r'^\d+\. ', '', l.strip()))}</li>" for l in bloc.splitlines()) + "</ol>")
            brut.extend(re.sub(r'^\d+\. ', '', l.strip()) for l in bloc.splitlines()); continue
        fermer_liste()
        texte = " ".join(l.strip() for l in bloc.splitlines())
        if en_faq:
            m = re.match(r"\*\*(.+?\?)\*\*\s*(.+)", texte)
            if m: faq.append((m.group(1), m.group(2)))
        out.append(f"<p>{inline(texte)}</p>"); brut.append(texte)
    fermer_liste()
    return "\n".join(out), faq, " ".join(brut)

def verifier(meta, corps):
    erreurs = []
    tout = " ".join(meta.values()) + corps
    if "—" in tout or "–" in tout: erreurs.append("tiret cadratin ou demi-cadratin présent")
    if len(meta.get("description","")) > 158: erreurs.append(f"meta trop longue ({len(meta['description'])} > 158)")
    if len(meta.get("titre","")) > 70: erreurs.append(f"titre trop long ({len(meta['titre'])} > 70)")
    for k in ("titre","description","slug","date","image","alt"):
        if not meta.get(k): erreurs.append(f"champ manquant : {k}")
    if re.search(r"\d\s?(€|euros?)\b", tout): erreurs.append("montant en euros : interdit (pas de prix inventé)")
    if not re.fullmatch(r"[a-z0-9-]+", meta.get("slug","")): erreurs.append("slug invalide (a-z, 0-9, tirets)")
    if not (RACINE / "photos" / meta.get("image","")).exists(): erreurs.append(f"image introuvable : photos/{meta.get('image')}")
    mots = len(re.findall(r"\w+", corps))
    if mots < 450: erreurs.append(f"article trop court ({mots} mots, minimum 450)")
    if erreurs: sys.exit("REFUSÉ : " + " ; ".join(erreurs))
    return mots

def charger_reg():
    return json.loads(REG.read_text(encoding="utf-8")) if REG.exists() else []

def sauver_reg(reg):
    reg.sort(key=lambda a: a["date"], reverse=True)
    REG.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")

def carte(a):
    return (f'<a class="carte" href="/blog/{a["slug"]}/"><img src="/photos/{a["image"]}" alt="{html.escape(a["alt"])}" loading="lazy" width="1200" height="750">'
            f'<div class="txt"><time datetime="{a["date"]}">{date_fr(a["date"])}</time><h3>{html.escape(a["titre"])}</h3><p>{html.escape(a["description"])}</p></div></a>')

def page_article(a, corps_html, faq, reg):
    autres = [x for x in reg if x["slug"] != a["slug"]][:3]
    schema = {"@context":"https://schema.org","@graph":[
        {"@type":"BlogPosting","@id":f"{SITE}/blog/{a['slug']}/#article","headline":a["titre"],"description":a["description"],
         "datePublished":a["date"],"dateModified":a.get("modifie",a["date"]),"inLanguage":"fr-FR",
         "image":f"{SITE}/photos/{a['image']}","wordCount":a["mots"],
         "author":{"@type":"Person","name":"Mathéo Grondin","url":f"{SITE}/","image":f"{SITE}/photos/matheo-portrait.jpg"},
         "publisher":{"@type":"Organization","name":"Jardin Péi","logo":{"@type":"ImageObject","url":f"{SITE}/logo.png"}},
         "mainEntityOfPage":f"{SITE}/blog/{a['slug']}/","about":{"@id":f"{SITE}/#entreprise"},
         "keywords":"entretien de jardin, espaces verts, Saint-Leu, L'Étang Saint-Leu, Piton Saint-Leu, Trois-Bassins, La Réunion"},
        {"@type":"BreadcrumbList","itemListElement":[
            {"@type":"ListItem","position":1,"name":"Accueil","item":f"{SITE}/"},
            {"@type":"ListItem","position":2,"name":"Conseils jardin","item":f"{SITE}/blog/"},
            {"@type":"ListItem","position":3,"name":a["titre"],"item":f"{SITE}/blog/{a['slug']}/"}]}]}
    if faq:
        schema["@graph"].append({"@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":r}} for q,r in faq]})
    lire = ""
    if autres:
        lire = '<section class="lire-aussi"><div class="wrap"><h2 class="filet centre">À lire aussi</h2><div class="cartes">' + "".join(carte(x) for x in autres) + '</div></div></section>'
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(a["titre"])} | Jardin Péi</title>
<meta name="description" content="{html.escape(a["description"])}">
<link rel="canonical" href="{SITE}/blog/{a["slug"]}/">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<link rel="alternate" type="application/rss+xml" title="Conseils jardin Jardin Péi" href="{SITE}/blog/flux.xml">
<meta property="og:type" content="article">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{html.escape(a["titre"])}">
<meta property="og:description" content="{html.escape(a["description"])}">
<meta property="og:image" content="{SITE}/photos/{a["image"]}">
<meta property="og:url" content="{SITE}/blog/{a["slug"]}/">
<meta property="article:published_time" content="{a["date"]}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@400;500;600;700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css?v=2">
<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=1)}
</script>
</head>
<body>
{HEADER}
<div class="page-tete">
  <div class="wrap">
    <p class="fil"><a href="/">Accueil</a> › <a href="/blog/">Conseils jardin</a></p>
    <h1>{html.escape(a["titre"])}</h1>
    <p class="meta">Par Mathéo, jardinier étudiant à L'Étang Saint-Leu · <time datetime="{a["date"]}">{date_fr(a["date"])}</time> · {a["mots"]} mots</p>
  </div>
</div>
<div class="article-couv"><img src="/photos/{a["image"]}" alt="{html.escape(a["alt"])}" width="1200" height="514"></div>

<article class="article">
{corps_html}
{ENCART}
<div class="auteur"><img src="/photos/matheo-jardinier-etang-saint-leu.png" alt="Mathéo, jardinier à L'Étang Saint-Leu" width="72" height="72"><div><b>Mathéo Grondin</b><span>Étudiant, j'entretiens les jardins des particuliers de L'Étang Saint-Leu, Saint-Leu, Piton Saint-Leu et Trois-Bassins. <a href="/#services">Voir mes services</a>.</span></div></div>
</article>

{lire}
{FOOTER}
</body>
</html>
"""

def page_liste(reg):
    schema = {"@context":"https://schema.org","@type":"Blog","@id":f"{SITE}/blog/#blog","name":"Conseils jardin par Jardin Péi",
              "description":"Conseils d'entretien de jardin à La Réunion par Mathéo, jardinier étudiant à L'Étang Saint-Leu.",
              "url":f"{SITE}/blog/","publisher":{"@id":f"{SITE}/#entreprise"},
              "blogPost":[{"@type":"BlogPosting","headline":a["titre"],"url":f"{SITE}/blog/{a['slug']}/","datePublished":a["date"]} for a in reg]}
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conseils d'entretien de jardin à La Réunion | Jardin Péi</title>
<meta name="description" content="Tonte, taille de haies, débroussaillage, déchets verts : les conseils de Mathéo, jardinier étudiant à L'Étang Saint-Leu, pour entretenir un jardin dans l'Ouest de La Réunion.">
<link rel="canonical" href="{SITE}/blog/">
<link rel="icon" type="image/svg+xml" href="/logo.svg">
<link rel="alternate" type="application/rss+xml" title="Conseils jardin Jardin Péi" href="{SITE}/blog/flux.xml">
<meta property="og:title" content="Conseils d'entretien de jardin à La Réunion | Jardin Péi">
<meta property="og:description" content="Les conseils de Mathéo pour entretenir un jardin à Saint-Leu, Piton Saint-Leu et Trois-Bassins.">
<meta property="og:image" content="{SITE}/photos/hero-jardinier-etang-saint-leu.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@400;500;600;700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css?v=2">
<script type="application/ld+json">
{json.dumps(schema, ensure_ascii=False, indent=1)}
</script>
</head>
<body>
{HEADER}
<div class="page-tete">
  <div class="wrap">
    <p class="fil"><a href="/">Accueil</a> › Conseils jardin</p>
    <h1>Conseils d'entretien de jardin à La Réunion</h1>
    <p class="meta">Les conseils de Mathéo, jardinier étudiant à L'Étang Saint-Leu, pour un jardin propre toute l'année dans l'Ouest : tonte, haies, débroussaillage, déchets verts.</p>
  </div>
</div>
<section>
  <div class="wrap">
    <div class="cartes" style="margin-top:0">
{"".join(carte(a) for a in reg)}
    </div>
  </div>
</section>
{FOOTER}
</body>
</html>
"""

def bloc_accueil(reg):
    if not reg: return ""
    return ('<section class="conseils" id="conseils">\n  <div class="wrap">\n    <h2 class="filet centre">Mes conseils pour votre jardin</h2>\n    <div class="cartes">'
            + "".join(carte(a) for a in reg[:3])
            + '</div>\n    <p class="centre" style="margin-top:36px"><a class="btn btn-ligne-sombre" href="/blog/">Tous les conseils</a></p>\n  </div>\n</section>')

def ecrire_accueil(reg):
    p = RACINE / "index.html"; s = p.read_text(encoding="utf-8")
    s = re.sub(r"<!-- DERNIERS-ARTICLES -->.*?<!-- /DERNIERS-ARTICLES -->",
               "<!-- DERNIERS-ARTICLES -->\n" + bloc_accueil(reg) + "\n<!-- /DERNIERS-ARTICLES -->", s, flags=re.S)
    p.write_text(s, encoding="utf-8")

def ecrire_sitemap(reg):
    auj = datetime.date.today().isoformat()
    urls = [f"  <url><loc>{SITE}/</loc><lastmod>{auj}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>",
            f"  <url><loc>{SITE}/blog/</loc><lastmod>{auj}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>"]
    for a in reg:
        urls.append(f"  <url><loc>{SITE}/blog/{a['slug']}/</loc><lastmod>{a.get('modifie',a['date'])}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority>"
                    f"<image:image><image:loc>{SITE}/photos/{a['image']}</image:loc><image:title>{html.escape(a['alt'])}</image:title></image:image></url>")
    (RACINE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n' + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")

def ecrire_rss(reg):
    items = "".join(f"<item><title>{html.escape(a['titre'])}</title><link>{SITE}/blog/{a['slug']}/</link><guid>{SITE}/blog/{a['slug']}/</guid>"
                    f"<pubDate>{datetime.datetime.fromisoformat(a['date']).strftime('%a, %d %b %Y 07:00:00 +0400')}</pubDate><description>{html.escape(a['description'])}</description></item>\n" for a in reg[:30])
    (RACINE / "blog" / "flux.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Conseils jardin Jardin Péi</title><link>{SITE}/blog/</link><description>Conseils d\'entretien de jardin à La Réunion par Mathéo, L\'Étang Saint-Leu.</description><language>fr</language>\n{items}</channel></rss>\n', encoding="utf-8")

def generer_tout(reg):
    for a in reg:
        meta, corps = lire_md(RACINE / "outils" / "articles" / f"{a['slug']}.md")
        corps_html, faq, _ = md_vers_html(corps)
        d = RACINE / "blog" / a["slug"]; d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page_article(a, corps_html, faq, reg), encoding="utf-8")
    (RACINE / "blog" / "index.html").write_text(page_liste(reg), encoding="utf-8")
    ecrire_accueil(reg); ecrire_sitemap(reg); ecrire_rss(reg)

def publier(urls):
    sh = lambda c: subprocess.run(c, shell=True, cwd=RACINE, check=True)
    sh('git add -A && git -c user.name="Romain Capdepont" -c user.email="capdepontromain@gmail.com" commit -q -m "Blog : ' + ", ".join(u.rsplit("/",2)[-2] for u in urls) + '\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" || true')
    sh("git push -q origin main")
    sh("rsync -az --delete --exclude .git --exclude .nojekyll --exclude CNAME --exclude .DS_Store ./ hostinger-pullup:domains/jardinpei.re/public_html/")
    ok = True
    for u in urls + [f"{SITE}/blog/", f"{SITE}/", f"{SITE}/sitemap.xml"]:
        try:
            code = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=20).status
        except Exception as e:
            code = getattr(e, "code", 0)
        print(f"{'OK ' if code==200 else 'KO '} {code} {u}"); ok = ok and code == 200
    subprocess.run(f"bash ~/seo/indexnow-submit.sh {' '.join(urls + [SITE + '/blog/'])}", shell=True)
    if not ok: sys.exit("Une URL ne répond pas 200 après publication")

def main():
    args = sys.argv[1:]
    pub = "--publier" in args; args = [a for a in args if a != "--publier"]
    reg = charger_reg(); nouveaux = []
    if "--regenerer" in args:
        generer_tout(reg)
    else:
        for chemin in args:
            meta, corps = lire_md(chemin)
            mots = verifier(meta, corps)
            if any(a["slug"] == meta["slug"] for a in reg) and not meta.get("maj"):
                sys.exit(f"REFUSÉ : slug déjà publié ({meta['slug']}). Ajouter « maj: oui » pour mettre à jour.")
            src = RACINE / "outils" / "articles" / f"{meta['slug']}.md"
            if pathlib.Path(chemin).resolve() != src.resolve(): src.write_text(pathlib.Path(chemin).read_text(encoding="utf-8"), encoding="utf-8")
            entree = {k: meta[k] for k in ("titre","description","slug","date","image","alt")}
            entree["mots"] = mots
            reg = [a for a in reg if a["slug"] != meta["slug"]]
            if meta.get("maj"): entree["modifie"] = datetime.date.today().isoformat()
            reg.append(entree); nouveaux.append(f"{SITE}/blog/{meta['slug']}/")
            print(f"généré : /blog/{meta['slug']}/ ({mots} mots{', FAQ' if md_vers_html(corps)[1] else ''})")
        sauver_reg(reg); reg = charger_reg(); generer_tout(reg)
    if pub: publier(nouveaux or [f"{SITE}/blog/"])

if __name__ == "__main__":
    main()
