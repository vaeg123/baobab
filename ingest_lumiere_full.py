#!/usr/bin/env python3
"""Ingestion TOTALE lumierejuridiqueabidjan — tous dossiers, tous formats."""
import asyncio, asyncpg, json, os, re, pathlib, sys, fitz
from datetime import date as ddate

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = os.environ["DATABASE_URL"]
ROOT = pathlib.Path("C:/Users/yboul/Desktop/lumierejuridiqueabidjan")

SKIP_NAMES = {"SERENITY", "Modele_", "Modèle_", "modele_", "__pycache__"}
SKIP_EXTS  = {".epub", ".csv", ".py", ".pyc", ".json"}


def should_skip(path: pathlib.Path) -> bool:
    n = path.name.upper()
    if any(s.upper() in n for s in SKIP_NAMES):
        return True
    if path.suffix.lower() in SKIP_EXTS:
        return True
    return False


def classify(path: pathlib.Path):
    """Retourne (type, corpus, domaine, pays) selon la position dans l'arborescence."""
    s = str(path).replace("\\", "/")
    p = path.name.lower()

    # ── Jurisprudence CI
    if "CI_Bail" in s or "bail" in p:
        return "decision_tca", "ci", "Bail et fonds de commerce", "Côte d'Ivoire"
    if "CI_Recou" in s or "recouvrement" in p:
        return "decision_tca", "ci", "Recouvrement de créances", "Côte d'Ivoire"
    if "CI_Societe" in s or "CI_SA" in s:
        return "decision_tca", "ci", "Droit des sociétés", "Côte d'Ivoire"
    if "Cautions" in s and "CI_" in path.name:
        return "decision_tca", "ci", "Cautions et garanties", "Côte d'Ivoire"
    if "Cautions" in s and "CRCA" in path.name.upper():
        return "decision_crca", "cima", "Cautions et garanties CIMA", "Zone CIMA"
    if "CRCA_Retrait" in s or "retrait" in p:
        return "decision_crca", "cima", "Retrait d'agrément CRCA", "Zone CIMA"
    if "Jurisprudence_CRCA" in s or "CRCA" in path.name.upper():
        return "decision_crca", "cima", "Jurisprudence CRCA", "Zone CIMA"
    if "Juridictions_ivoiriennes" in s and ("Cartographie" in path.name or "Inventaire" in path.name):
        return "synthese", "ci", "Cartographie jurisprudence ivoirienne", "Côte d'Ivoire"
    if "04_Jurisprudence" in s:
        return "decision_tca", "ci", "Droit ivoirien", "Côte d'Ivoire"

    # ── OHADA
    if "02_Droit_OHADA" in s:
        dom = "Droit OHADA"
        if "societe" in p:     dom = "Droit des sociétés OHADA"
        if "surete" in p:      dom = "Sûretés OHADA"
        if "recouvrement" in p: dom = "Recouvrement OHADA"
        if "collective" in p:  dom = "Procédures collectives OHADA"
        if "comptable" in p or "comptabilite" in p: dom = "Comptabilité OHADA"
        if "commercial" in p:  dom = "Droit commercial OHADA"
        dt = "doctrine" if "Doctrine" in s else "synthese"
        return dt, "ohada", dom, "Zone OHADA"

    # ── CIMA
    if "03_Droit_CIMA" in s:
        dom = "Droit des assurances CIMA"
        if "caution" in p:  dom = "Cautions et garanties CIMA"
        if "sanction" in p: dom = "Sanctions CRCA"
        if "obligation" in p: dom = "Obligations sociétés d'assurance"
        dt = "doctrine" if "Doctrine" in s else "synthese"
        return dt, "cima", dom, "Zone CIMA"

    # ── Droit CI entreprises
    if "01_Droit_des_entreprises" in s:
        dom = "Droit des entreprises CI"
        if "fiscalite" in p or "fiscal" in p: dom = "Fiscalité des entreprises CI"
        if "creation" in p: dom = "Création d'entreprise CI"
        if "dirigeant" in p: dom = "Responsabilité des dirigeants CI"
        if "preuve" in p or "contentieux" in p: dom = "Contentieux commercial CI"
        dt = "doctrine" if "Doctrine" in s else "synthese"
        return dt, "ci", dom, "Côte d'Ivoire"

    # ── Droit famille / patrimoine
    if "09_Droit_famille" in s:
        dom = "Droit de la famille CI"
        if "succession" in p or "decedes" in p or "deces" in p: dom = "Successions CI"
        if "communaute" in p or "patrimoine" in p: dom = "Régimes matrimoniaux CI"
        return "synthese", "ci", dom, "Côte d'Ivoire"

    # ── Doctrine & recherche
    if "05_Doctrine" in s:
        if "these" in p or "memoire" in p or "these" in s.lower():
            return "these", "ohada", "Méthodologie juridique", "Zone OHADA"
        return "doctrine", "ohada", "Doctrine juridique", "Zone OHADA"

    # ── Bibliographie
    if "08_Bibliographie" in s:
        return "synthese", "ohada", "Bibliographie juridique", "Zone OHADA"

    # ── Tableau de bord
    if "00_Tableau_de_bord" in s:
        return "synthese", "ohada", "Index et plan de recherche", "Zone OHADA"

    return "doctrine", "ci", "Droit ivoirien", "Côte d'Ivoire"


def parse_md(text: str):
    def g(pat):
        m = re.search(pat, text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    ref      = g(r"- R[eé]f[eé]rence\s*:\s*(.+)")
    date_raw = g(r"- Date\s*:\s*([\d\-/]+)")
    juri     = g(r"- Juridiction\s*:\s*(.+)")
    parts    = g(r"- Parties\s*:\s*(.+)")
    mots_raw = g(r"- Mots-cles\s*:\s*(.+)")
    mots = [x.strip() for x in mots_raw.split(";") if x.strip()] if mots_raw else []

    parties = {}
    if parts:
        p = [x.strip() for x in parts.split(";")]
        if len(p) >= 2:
            parties = {"demandeur": p[0], "defenseur": p[1]}

    titre = g(r"^# (.+)")
    resume = g(r"## Solution[^\n]*\n(.+?)(?:\n##|\Z)")
    if not resume:
        resume = g(r"## Probl[eè]me juridique[^\n]*\n(.+?)(?:\n##|\Z)")
    if not resume:
        # Prendre les 3 premiers paragraphes non-vides
        paras = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#") and not l.startswith("-")]
        resume = " ".join(paras[:3])

    date_dec = None
    if re.match(r"\d{4}-\d{2}-\d{2}", date_raw or ""):
        try:
            y, mo, d = date_raw.split("-")
            date_dec = ddate(int(y), int(mo), int(d))
        except Exception:
            pass

    return ref, titre, juri, parties, mots, resume[:600], date_dec


async def ingest_md(conn, path: pathlib.Path):
    if should_skip(path): return False, "skip"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text.strip()) < 50: return False, "empty"

    ref, titre, juri, parties, mots, resume, date_dec = parse_md(text)
    if not ref: ref = path.stem[:200]
    if not titre: titre = path.stem.replace("_", " ")[:200]

    ex = await conn.fetchval("SELECT id FROM legal_corpus WHERE ref=$1", ref)
    if ex: return False, "dup"

    doc_type, corpus, domaine, pays = classify(path)

    await conn.execute(
        """INSERT INTO legal_corpus
           (ref,type,corpus,juridiction,titre,date_decision,parties,
            pays,domaine,resume,texte_integral,mots_cles,metadata)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
        ref, doc_type, corpus,
        juri or ("Tribunal de Commerce Abidjan" if corpus == "ci" else ""),
        titre, date_dec,
        json.dumps(parties, ensure_ascii=False),
        pays, domaine, resume, text[:60000], mots,
        json.dumps({"source": "lumierejuridiqueabidjan", "fichier": path.name}),
    )
    return True, f"[{corpus}:{doc_type}]"


async def ingest_pdf(conn, path: pathlib.Path):
    if should_skip(path): return False, "skip"
    ref = path.stem[:200]
    ex = await conn.fetchval("SELECT id FROM legal_corpus WHERE ref=$1", ref)
    if ex: return False, "dup"

    try:
        doc = fitz.open(str(path))
        text = "".join(page.get_text() for page in doc)[:60000]
        doc.close()
    except Exception as e:
        return False, f"err:{e}"

    if len(text.strip()) < 100: return False, "empty"

    doc_type, corpus, domaine, pays = classify(path)

    await conn.execute(
        """INSERT INTO legal_corpus
           (ref,type,corpus,titre,pays,domaine,resume,texte_integral,metadata)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
        ref, doc_type, corpus,
        path.name[:200], pays, domaine,
        text[:600], text,
        json.dumps({"source": "lumierejuridiqueabidjan", "fichier": path.name}),
    )
    return True, f"[{corpus}:{doc_type}]"


async def run():
    conn = await asyncpg.connect(DB)
    inserted = skipped = errors = 0

    # Collecter tous les fichiers
    all_files = sorted(
        f for f in ROOT.rglob("*")
        if f.is_file() and f.suffix.lower() in {".md", ".pdf", ".txt"}
        and "__pycache__" not in str(f)
    )
    print(f"Fichiers totaux : {len(all_files)}")

    for f in all_files:
        try:
            if f.suffix.lower() == ".pdf":
                ok, info = await ingest_pdf(conn, f)
            else:
                ok, info = await ingest_md(conn, f)

            if ok:
                inserted += 1
                print(f"  OK {info} {f.name}")
            elif info == "dup":
                skipped += 1
            elif info == "skip" or info == "empty":
                skipped += 1
            else:
                errors += 1
                print(f"  ERR {info} — {f.name}")
        except Exception as e:
            errors += 1
            print(f"  FATAL {f.name}: {e}")

    total = await conn.fetchval("SELECT COUNT(*) FROM legal_corpus")
    await conn.close()

    print(f"\n{'='*55}")
    print(f"Insérés  : {inserted}")
    print(f"Ignorés  : {skipped}")
    print(f"Erreurs  : {errors}")
    print(f"TOTAL DB : {total}")


asyncio.run(run())
