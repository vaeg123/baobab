#!/usr/bin/env python3
"""Insère les Actes Uniformes OHADA et textes CCJA depuis biblio.ohada.org.
Usage: DATABASE_URL=... python ingest_ohada_au.py
"""
import asyncio, asyncpg, json, os, sys, urllib.request
from datetime import date as ddate
import fitz
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = os.environ["DATABASE_URL"]

# ── Documents avec texte extractible ─────────────────────────────────────
TEXT_DOCS = [
    {
        "ref": "AUPCAP-2015",
        "explnum_id": 19,
        "titre": "Acte Uniforme portant organisation des Procédures Collectives d'Apurement du Passif (2015)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Procédures collectives OHADA",
        "pays": "Zone OHADA",
        "date": "2015-09-10",
    },
    {
        "ref": "AUSCGIE-2014",
        "explnum_id": 2032,
        "titre": "Acte Uniforme relatif au Droit des Sociétés Commerciales et du GIE (2014)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Droit des sociétés OHADA",
        "pays": "Zone OHADA",
        "date": "2014-01-30",
    },
    {
        "ref": "AUDCIF-2017",
        "explnum_id": 2061,
        "titre": "Acte Uniforme relatif au Droit Comptable et à l'Information Financière (2017)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Comptabilité OHADA",
        "pays": "Zone OHADA",
        "date": "2017-01-26",
    },
    {
        "ref": "CCJA-Reglement-Arbitrage",
        "explnum_id": 14,
        "titre": "Règlement d'Arbitrage de la CCJA-OHADA",
        "type": "reglement",
        "corpus": "ohada",
        "juridiction": "CCJA",
        "domaine": "Arbitrage OHADA",
        "pays": "Zone OHADA",
        "date": "1999-01-23",
    },
    {
        "ref": "CCJA-Reglement-Procedure",
        "explnum_id": 15,
        "titre": "Règlement de Procédure de la CCJA-OHADA",
        "type": "reglement",
        "corpus": "ohada",
        "juridiction": "CCJA",
        "domaine": "Arbitrage OHADA",
        "pays": "Zone OHADA",
        "date": "1996-04-01",
    },
]

# ── Documents image (texte non extractible) — on insère les métadonnées ──
IMAGE_DOCS = [
    {
        "ref": "AUDCG-2010",
        "explnum_id": 6,
        "titre": "Acte Uniforme relatif au Droit Commercial Général (2010)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Droit commercial OHADA",
        "pays": "Zone OHADA",
        "date": "2010-12-15",
        "resume": "L'Acte Uniforme relatif au Droit Commercial Général (AUDCG) adopté à Lomé le 15 décembre 2010 régit le statut du commerçant, l'entrepreneur individuel, le registre du commerce et du crédit mobilier (RCCM), le bail professionnel, le fonds de commerce, les intermédiaires de commerce et la vente commerciale. Il s'applique aux États membres de l'OHADA.",
    },
    {
        "ref": "AUS-2010",
        "explnum_id": 483,
        "titre": "Acte Uniforme portant organisation des Sûretés (2010)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Sûretés OHADA",
        "pays": "Zone OHADA",
        "date": "2010-12-15",
        "resume": "L'Acte Uniforme portant organisation des Sûretés (AUS) adopté à Lomé le 15 décembre 2010 organise les sûretés personnelles (cautionnement, garantie autonome, lettre d'intention) et réelles (hypothèques, nantissements, gages) en droit OHADA. Il modernise la réglementation des garanties et du crédit.",
    },
    {
        "ref": "AUSCOOP-2010",
        "explnum_id": 487,
        "titre": "Acte Uniforme relatif au Droit des Sociétés Coopératives (2010)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Droit des sociétés OHADA",
        "pays": "Zone OHADA",
        "date": "2010-12-15",
        "resume": "L'Acte Uniforme relatif au Droit des Sociétés Coopératives (AUSCOOP) adopté à Lomé le 15 décembre 2010 définit le cadre juridique des coopératives simples et des coopératives avec conseil d'administration dans l'espace OHADA.",
    },
    {
        "ref": "AUCTMR-2003",
        "explnum_id": 482,
        "titre": "Acte Uniforme relatif aux Contrats de Transport de Marchandises par Route (2003)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Droit commercial OHADA",
        "pays": "Zone OHADA",
        "date": "2003-03-22",
        "resume": "L'Acte Uniforme relatif aux Contrats de Transport de Marchandises par Route (AUCTMR) adopté à Yaoundé le 22 mars 2003 régit la lettre de voiture, les obligations du transporteur, la responsabilité en cas de perte ou avarie et les délais de livraison.",
    },
    {
        "ref": "AUPSRVE-1998",
        "explnum_id": 485,
        "titre": "Acte Uniforme portant organisation des Procédures Simplifiées de Recouvrement et des Voies d'Exécution (1998)",
        "type": "acte_uniforme",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Recouvrement OHADA",
        "pays": "Zone OHADA",
        "date": "1998-04-10",
        "resume": "L'AUPSRVE de 1998 organise les procédures d'injonction de payer, l'injonction de délivrer ou de restituer, et les différentes voies d'exécution (saisies conservatoires, saisies-attribution, saisie immobilière). Il a été révisé en 2023 (AUPSRVE-2023).",
    },
    {
        "ref": "Traité-OHADA-1993",
        "explnum_id": 12,
        "titre": "Traité relatif à l'Harmonisation du Droit des Affaires en Afrique (Port-Louis, 1993)",
        "type": "traite",
        "corpus": "ohada",
        "juridiction": "OHADA",
        "domaine": "Droit OHADA",
        "pays": "Zone OHADA",
        "date": "1993-10-17",
        "resume": "Le Traité OHADA signé à Port-Louis (Maurice) le 17 octobre 1993 institue l'Organisation pour l'Harmonisation en Afrique du Droit des Affaires. Il crée les institutions (Conseil des Ministres, CCJA, ERSUMA) et définit le cadre des Actes Uniformes adoptés par le Conseil des Ministres.",
    },
]


def download_pdf(explnum_id: int) -> bytes | None:
    url = f"http://biblio.ohada.org/pmb/opac_css/doc_num.php?explnum_id={explnum_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def extract_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return text


def parse_date(s: str):
    y, m, d = s.split("-")
    return ddate(int(y), int(m), int(d))


async def upsert(conn, ref, doc_type, corpus, juridiction, titre, date_str, pays, domaine, resume, texte, meta):
    date_obj = parse_date(date_str)
    ex = await conn.fetchval("SELECT id FROM legal_corpus WHERE ref=$1", ref)
    if ex:
        has_text = await conn.fetchval(
            "SELECT length(texte_integral) > 200 FROM legal_corpus WHERE ref=$1", ref
        )
        if has_text:
            return "dup"
        await conn.execute(
            "UPDATE legal_corpus SET texte_integral=$1, resume=$2 WHERE ref=$3",
            texte[:80000], resume[:600], ref,
        )
        return "updated"
    await conn.execute(
        """INSERT INTO legal_corpus
           (ref,type,corpus,juridiction,titre,date_decision,pays,domaine,
            resume,texte_integral,metadata)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
        ref, doc_type, corpus, juridiction, titre, date_obj, pays, domaine,
        resume[:600], texte[:80000],
        json.dumps(meta, ensure_ascii=False),
    )
    return "inserted"


async def run():
    conn = await asyncpg.connect(DB)
    inserted = updated = skipped = errors = 0

    # ── 1. Documents texte ─────────────────────────────────────────────
    print("=== Actes Uniformes (texte extractible) ===")
    for doc in TEXT_DOCS:
        ref = doc["ref"]
        print(f"\n→ {ref}")
        try:
            pdf = download_pdf(doc["explnum_id"])
            text = extract_text(pdf)
            print(f"  {len(pdf)//1024}KB → {len(text)} chars")
            if len(text.strip()) < 100:
                print("  WARNING: very little text extracted")
                text = f"[Texte image — PDF biblio.ohada.org explnum_id={doc['explnum_id']}]"
            meta = {"source": "biblio.ohada.org", "explnum_id": doc["explnum_id"]}
            status = await upsert(
                conn, ref, doc["type"], doc["corpus"], doc["juridiction"],
                doc["titre"], doc["date"], doc["pays"], doc["domaine"],
                text[:600], text, meta,
            )
            print(f"  {status.upper()}")
            if status == "inserted": inserted += 1
            elif status == "updated": updated += 1
            else: skipped += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR: {e}")

    # ── 2. Documents image — métadonnées seules ────────────────────────
    print("\n=== Actes Uniformes (PDF image — métadonnées) ===")
    for doc in IMAGE_DOCS:
        ref = doc["ref"]
        print(f"\n→ {ref}")
        try:
            meta = {
                "source": "biblio.ohada.org",
                "explnum_id": doc["explnum_id"],
                "texte_note": "PDF image — OCR requis",
            }
            resume = doc.get("resume", f"Texte non extractible. Voir explnum_id={doc['explnum_id']}.")
            texte = f"[Texte non extractible — PDF scanné. Source: biblio.ohada.org explnum_id={doc['explnum_id']}]\n\n{resume}"
            status = await upsert(
                conn, ref, doc["type"], doc["corpus"], doc["juridiction"],
                doc["titre"], doc["date"], doc["pays"], doc["domaine"],
                resume, texte, meta,
            )
            print(f"  {status.upper()}")
            if status == "inserted": inserted += 1
            elif status == "updated": updated += 1
            else: skipped += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR: {e}")

    total = await conn.fetchval("SELECT COUNT(*) FROM legal_corpus")
    au_count = await conn.fetchval(
        "SELECT COUNT(*) FROM legal_corpus WHERE type IN ('acte_uniforme','reglement','traite')"
    )
    await conn.close()
    print(f"\n{'='*55}")
    print(f"Insérés    : {inserted}")
    print(f"Mis à jour : {updated}")
    print(f"Ignorés    : {skipped}")
    print(f"Erreurs    : {errors}")
    print(f"AUs/Règl.  : {au_count}")
    print(f"TOTAL DB   : {total}")


asyncio.run(run())
