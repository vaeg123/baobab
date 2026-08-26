"""Moteur prudent de détection des nouveautés sur les sources juridiques officielles."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from baobab.api.routes.legal import _conn
from baobab.config import settings
from baobab.notifications import notify_legal_watch_alert


@dataclass(frozen=True)
class WatchSource:
    code: str
    name: str
    corpus: str
    discovery_url: str
    parser: str
    fallback_urls: tuple[str, ...] = ()
    document_type: str | None = None
    country_code: str | None = None
    jurisdiction_code: str | None = None
    pagination_starts: tuple[int, ...] = ()


@dataclass(frozen=True)
class Artifact:
    source_code: str
    corpus: str
    url: str
    title: str
    legal_date: date | None = None
    date_precision: str = "UNKNOWN"

    @property
    def checksum(self) -> str:
        normalized = "\n".join((self.title.strip(), self.url.strip(), str(self.legal_date or "")))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


WATCH_SOURCES = (
    WatchSource(
        code="OHADA.BIBLIO",
        name="Bibliothèque OHADA — jurisprudence CCJA",
        corpus="ohada",
        discovery_url=(
            "https://biblio.ohada.org/index.php?"
            "search_type_asked=simple_search&look_for=arret+CCJA"
        ),
        parser="ohada_biblio",
    ),
    WatchSource(
        code="CIMA.OFFICIAL",
        name="CIMA — décisions de la CRCA",
        corpus="cima",
        discovery_url="https://www.cima-afrique.org/decisions-de-la-crca/",
        parser="cima_crca",
        fallback_urls=("https://cima-afrique.org/document-category/decisions-de-la-crca/",),
    ),
    WatchSource(
        code="CM.PRC.LOIS", name="Présidence du Cameroun — Lois", corpus="cm",
        discovery_url="https://www.prc.cm/fr/actualites/actes/lois", parser="cameroon_prc",
        document_type="loi", country_code="CM", jurisdiction_code="CM",
        pagination_starts=(8, 16),
    ),
    WatchSource(
        code="CM.PRC.ORDONNANCES", name="Présidence du Cameroun — Ordonnances", corpus="cm",
        discovery_url="https://www.prc.cm/fr/actualites/actes/ordonnances", parser="cameroon_prc",
        document_type="ordonnance", country_code="CM", jurisdiction_code="CM",
        pagination_starts=(8, 16),
    ),
    WatchSource(
        code="CM.PRC.DECRETS", name="Présidence du Cameroun — Décrets", corpus="cm",
        discovery_url="https://www.prc.cm/fr/actualites/actes/decrets", parser="cameroon_prc",
        document_type="decret", country_code="CM", jurisdiction_code="CM",
        pagination_starts=(8, 16),
    ),
    WatchSource(
        code="CM.MINJUSTICE.CASELAW", name="MINJUSTICE Cameroun — Décisions", corpus="cm",
        discovery_url="https://www.minjustice.gov.cm/index.php/fr/e-justice/decisions-de-justice",
        parser="cameroon_minjustice", document_type="decision_juridictionnelle",
        country_code="CM", jurisdiction_code="CM.SUPREME",
    ),
    WatchSource(
        code="CM.JURICAF.SEARCH", name="JURICAF — jurisprudence camerounaise", corpus="cm",
        discovery_url="https://juricaf.org/recherche/pays:cameroun",
        parser="juricaf_cm", document_type="arret", country_code="CM",
        jurisdiction_code="CM.SUPREME",
        fallback_urls=("https://juricaf.org/recherche/cameroun",),
        pagination_starts=(10, 20),
    ),
)

_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "decembre": 12,
}


def _parse_french_date(value: str) -> tuple[date | None, str]:
    normalized = " ".join(value.lower().split())
    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", normalized)
    if iso:
        try:
            return date(int(iso[1]), int(iso[2]), int(iso[3])), "DAY"
        except ValueError:
            return None, "UNKNOWN"
    written = re.search(r"\b(\d{1,2})(?:er|ème|eme|re)?\s+([a-zéûôîàèùç]+)\s+(20\d{2})\b", normalized)
    if written and written[2] in _MONTHS:
        try:
            return date(int(written[3]), _MONTHS[written[2]], int(written[1])), "DAY"
        except ValueError:
            return None, "UNKNOWN"
    year = re.search(r"\b(20\d{2})\b", normalized)
    return (date(int(year[1]), 1, 1), "YEAR") if year else (None, "UNKNOWN")


def parse_ohada_biblio(html: str, source: WatchSource) -> list[Artifact]:
    soup = BeautifulSoup(html, "html.parser")
    artifacts: dict[str, Artifact] = {}
    for link in soup.select("a[href*='notice_display&id=']"):
        href = str(link.get("href") or "")
        match = re.search(r"(?:[?&])id=(\d+)", href)
        if not match:
            continue
        url = f"https://biblio.ohada.org/index.php?lvl=notice_display&id={match[1]}"
        title = " ".join(link.get_text(" ", strip=True).split())
        generic = {"", "Plus d'information...", "Non prêtable", "Voir la notice"}
        if title in generic:
            continue
        legal_date, precision = _parse_french_date(title)
        candidate = Artifact(
            source.code, source.corpus, url, title, legal_date, precision
        )
        current = artifacts.get(url)
        if current is None or len(candidate.title) > len(current.title):
            artifacts[url] = candidate
    return sorted(artifacts.values(), key=lambda item: item.url)


def parse_cima_crca(html: str, source: WatchSource) -> list[Artifact]:
    soup = BeautifulSoup(html, "html.parser")
    artifacts: dict[str, Artifact] = {}
    for row in soup.select("tr"):
        link = row.select_one("a[href$='.pdf'], a[href*='.pdf?']")
        if not link:
            continue
        url = urljoin(source.discovery_url, str(link.get("href") or ""))
        title = " ".join(link.get_text(" ", strip=True).split())
        row_text = " ".join(row.get_text(" ", strip=True).split())
        legal_date, precision = _parse_french_date(row_text)
        artifacts[url] = Artifact(
            source.code, source.corpus, url, title or row_text[:180], legal_date, precision
        )
    # Le site CIMA expose aussi les décisions sous forme de cartes menant à
    # une fiche officielle, notamment lorsque la page historique est lente.
    for link in soup.select("a[href]"):
        title = " ".join(link.get_text(" ", strip=True).split())
        if not re.search(r"\bd[ée]cision\b", title, re.IGNORECASE):
            continue
        url = urljoin(source.discovery_url, str(link.get("href") or ""))
        if "cima-afrique.org" not in url.lower():
            continue
        legal_date, precision = _parse_french_date(title)
        if url not in artifacts:
            artifacts[url] = Artifact(
                source.code, source.corpus, url, title[:500], legal_date, precision
            )
    return sorted(artifacts.values(), key=lambda item: item.url)


def parse_cameroon_prc(html: str, source: WatchSource) -> list[Artifact]:
    """Extrait uniquement les fiches d'actes de la liste officielle PRC."""
    soup = BeautifulSoup(html, "html.parser")
    artifacts: dict[str, Artifact] = {}
    expected_path = f"/fr/actualites/actes/{source.discovery_url.rstrip('/').split('/')[-1]}/"
    for link in soup.select("h3 a[href], h4 a[href], .item-title a[href]"):
        title = " ".join(link.get_text(" ", strip=True).split())
        url = urljoin(source.discovery_url, str(link.get("href") or ""))
        if expected_path not in url or len(title) < 12:
            continue
        legal_date, precision = _parse_french_date(title)
        artifacts[url] = Artifact(
            source.code, source.corpus, url, title[:500], legal_date, precision
        )
    return sorted(artifacts.values(), key=lambda item: item.url)


def parse_juricaf_cm(html: str, source: WatchSource) -> list[Artifact]:
    """Extrait les arrêts camerounais de JURICAF.

    JURICAF expose les décisions sous deux structures HTML selon la page :
    - Résultats de recherche : liens /arret/CAMEROUN-… dans des conteneurs
      .resultat, li, ou td — le titre est dans le texte du lien.
    - Page d'accueil pays : cartes similaires avec /arret/CAMEROUN-…
    Seuls les liens dont l'URL contient /arret/ et CAMEROUN (majuscules ou non)
    sont retenus ; les liens de navigation internes sont rejetés.
    """
    soup = BeautifulSoup(html, "html.parser")
    artifacts: dict[str, Artifact] = {}
    for link in soup.select("a[href*='/arret/']"):
        href = str(link.get("href") or "")
        if "cameroun" not in href.lower():
            continue
        url = urljoin("https://juricaf.org", href).split("?")[0].rstrip("/")
        if not re.search(r"/arret/[A-Z]", url, re.IGNORECASE):
            continue
        title = " ".join(link.get_text(" ", strip=True).split())
        if len(title) < 10:
            # Le texte du lien est trop court — on tente le parent immédiat
            parent_text = " ".join((link.parent or link).get_text(" ", strip=True).split())
            if len(parent_text) >= 10:
                title = parent_text[:500]
        if len(title) < 10:
            continue
        legal_date, precision = _parse_french_date(title)
        if url not in artifacts:
            artifacts[url] = Artifact(
                source.code, source.corpus, url, title[:500], legal_date, precision
            )
    return sorted(artifacts.values(), key=lambda item: item.url)


def parse_cameroon_minjustice(html: str, source: WatchSource) -> list[Artifact]:
    """Parseur restrictif : seules les fiches/PDF explicitement juridictionnels passent."""
    soup = BeautifulSoup(html, "html.parser")
    artifacts: dict[str, Artifact] = {}
    for link in soup.select("a[href]"):
        title = " ".join(link.get_text(" ", strip=True).split())
        if not re.search(r"\b(arr[êe]t|jugement|ordonnance|d[ée]cision)\b", title, re.I):
            continue
        url = urljoin(source.discovery_url, str(link.get("href") or ""))
        if ("minjustice.gov.cm" not in url.lower() or len(title) < 12
                or title.lower() in {"décisions de justice", "decisions de justice"}
                or url.rstrip("/") == source.discovery_url.rstrip("/")):
            continue
        legal_date, precision = _parse_french_date(title)
        artifacts[url] = Artifact(
            source.code, source.corpus, url, title[:500], legal_date, precision
        )
    return sorted(artifacts.values(), key=lambda item: item.url)


def parse_source(html: str, source: WatchSource) -> list[Artifact]:
    parsers = {
        "ohada_biblio": parse_ohada_biblio,
        "cima_crca": parse_cima_crca,
        "cameroon_prc": parse_cameroon_prc,
        "cameroon_minjustice": parse_cameroon_minjustice,
        "juricaf_cm": parse_juricaf_cm,
    }
    return parsers[source.parser](html, source)


def watch_matches_artifact(watch: dict, artifact: Artifact) -> bool:
    corpus = str(watch.get("corpus") or "all").lower()
    corpus_aliases = {
        "ohada": {"ohada", "ccja"}, "cima": {"cima", "crca"},
        "bceao": {"bceao", "uemoa"}, "bceao_uemoa": {"bceao", "uemoa"},
        "cameroun": {"cm", "cameroun"}, "cm": {"cm", "cameroun"},
    }
    if corpus != "all" and artifact.corpus not in corpus_aliases.get(corpus, {corpus}):
        return False
    query = str(watch.get("query") or "").strip().lower()
    if not query:
        return True
    terms = [term.strip() for term in re.split(r"[,;]", query) if term.strip()]
    haystack = f"{artifact.title} {artifact.url}".lower()
    return any(term in haystack for term in terms)


def score_artifact_validation(
    artifact: Artifact, consecutive_observations: int, *, official_source: bool = True
) -> tuple[int, list[str]]:
    """Calcule un score déterministe de fiabilité documentaire, jamais juridique."""
    score = 0
    reasons: list[str] = []
    if official_source:
        score += 40
        reasons.append("SOURCE_OFFICIELLE_ENREGISTREE:+40")
    if consecutive_observations >= 2:
        score += 20
        reasons.append("DOCUMENT_STABLE_SUR_2_CYCLES:+20")
    else:
        reasons.append("SECONDE_OBSERVATION_REQUISE:+0")
    generic = {"document", "publication", "décision", "decision", "voir la notice"}
    if len(artifact.title.strip()) >= 15 and artifact.title.strip().lower() not in generic:
        score += 15
        reasons.append("TITRE_DOCUMENTAIRE_EXPLOITABLE:+15")
    if re.search(
        r"\b(arr[êe]t|jugement|loi|ordonnance|d[ée]cret|arr[êe]t[ée]|d[ée]cision|circulaire)"
        r"\s*(?:n[°o]|no|num[ée]ro)?\s*\d",
        artifact.title, re.I,
    ):
        score += 15
        reasons.append("REFERENCE_JURIDIQUE_RECONNUE:+15")
    if artifact.legal_date and artifact.legal_date <= date.today() + timedelta(days=2):
        score += 10
        reasons.append("DATE_JURIDIQUE_PLAUSIBLE:+10")
    else:
        reasons.append("DATE_JURIDIQUE_ABSENTE_OU_INCOHERENTE:+0")
    return score, reasons


def extract_official_reference(title: str) -> str | None:
    match = re.search(
        r"\b(?:loi|ordonnance|d[ée]cret|arr[êe]t[ée]|d[ée]cision|circulaire|arr[êe]t|jugement)"
        r"\s*(?:n[°o]|no|num[ée]ro)?\s*([0-9]{1,4}(?:[/\-][0-9A-Za-z]{1,6})+)",
        title, re.I,
    )
    return match.group(0).strip() if match else None


def infer_change_type(title: str) -> str | None:
    normalized = title.lower()
    rules = (
        ("abrog", "REPEALS"), ("modifi", "AMENDS"), ("complét", "SUPPLEMENTS"),
        ("ratifi", "RATIFIES"), ("application", "IMPLEMENTS"),
        ("portant", "ENACTS"),
    )
    return next((label for needle, label in rules if needle in normalized), None)


async def _fetch_source(
    client: httpx.AsyncClient, source: WatchSource
) -> tuple[WatchSource, str, str, list[str]]:
    errors: list[str] = []
    urls = (source.discovery_url, *source.fallback_urls)
    for url_index, url in enumerate(urls):
        attempts = 2 if url_index == 0 else 1
        for attempt in range(attempts):
            try:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "BAOBAB-Legal-Watch/1.1 (+https://vaegbaobab.com)",
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "fr-FR,fr;q=0.9",
                    },
                )
                response.raise_for_status()
                pages = [response.text]
                for start in source.pagination_starts:
                    separator = "&" if "?" in url else "?"
                    page_url = f"{url}{separator}start={start}"
                    try:
                        page_response = await client.get(page_url, headers={
                            "User-Agent": "BAOBAB-Legal-Watch/1.1 (+https://vaegbaobab.com)",
                            "Accept": "text/html,application/xhtml+xml",
                            "Accept-Language": "fr-FR,fr;q=0.9",
                        })
                        page_response.raise_for_status()
                        pages.append(page_response.text)
                    except (httpx.TimeoutException, httpx.HTTPError) as page_exc:
                        errors.append(f"{page_url}: {type(page_exc).__name__}")
                return source, "\n".join(pages), str(response.url), errors
            except (httpx.TimeoutException, httpx.HTTPError) as exc:
                errors.append(f"{url} [{attempt + 1}/{attempts}]: {type(exc).__name__}")
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
    raise RuntimeError("; ".join(errors))


async def run_watch_cycle(trigger: str = "manual") -> dict:
    """Exécute un cycle idempotent, journalisé et protégé contre le chevauchement."""
    run_id = f"run_{uuid4().hex[:20]}"
    conn = await _conn()
    lock_acquired = False
    stats = {
        "run_id": run_id, "trigger": trigger, "status": "RUNNING",
        "sources_checked": len(WATCH_SOURCES), "sources_succeeded": 0,
        "sources_failed": 0, "artifacts_seen": 0, "events_created": 0,
        "events_auto_validated": 0, "matches_created": 0, "emails_sent": 0,
        "sources": [],
    }
    try:
        lock_acquired = bool(await conn.fetchval("SELECT pg_try_advisory_lock($1)", 7240202601))
        if not lock_acquired:
            return {**stats, "status": "SKIPPED_ALREADY_RUNNING"}
        await conn.execute(
            "INSERT INTO legal_watch_runs (run_id, trigger, status, sources_checked) VALUES ($1,$2,'RUNNING',$3)",
            run_id, trigger, len(WATCH_SOURCES),
        )
        timeout = httpx.Timeout(12.0, connect=6.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            fetched = await asyncio.gather(
                *(_fetch_source(client, source) for source in WATCH_SOURCES),
                return_exceptions=True,
            )

        watches = [dict(row) for row in await conn.fetch(
            "SELECT * FROM legal_watch_subscriptions WHERE active = TRUE"
        )]
        for source, result in zip(WATCH_SOURCES, fetched, strict=True):
            if isinstance(result, Exception):
                error_label = f"{type(result).__name__}: {result}".strip()
                stats["sources_failed"] += 1
                stats["sources"].append({"code": source.code, "status": "FAILED", "error": error_label[:300]})
                await conn.execute(
                    """INSERT INTO legal_source_snapshots
                       (source_code, discovery_url, last_checked_at, last_status, last_error)
                       VALUES ($1,$2,NOW(),'FAILED',$3)
                       ON CONFLICT (source_code) DO UPDATE SET last_checked_at=NOW(),
                       last_status='FAILED', last_error=EXCLUDED.last_error, updated_at=NOW()""",
                    source.code, source.discovery_url, error_label[:1000],
                )
                continue

            _, html, effective_url, fetch_warnings = result
            try:
                artifacts = parse_source(html, source)
                if not artifacts:
                    raise ValueError("Aucun document reconnu dans la page source")
            except Exception as exc:
                error_label = f"{type(exc).__name__}: {exc}".strip()
                stats["sources_failed"] += 1
                stats["sources"].append(
                    {"code": source.code, "status": "FAILED", "error": error_label[:300]}
                )
                await conn.execute(
                    """INSERT INTO legal_source_snapshots
                       (source_code, discovery_url, last_checked_at, last_status, last_error)
                       VALUES ($1,$2,NOW(),'FAILED',$3)
                       ON CONFLICT (source_code) DO UPDATE SET last_checked_at=NOW(),
                       last_status='FAILED', last_error=EXCLUDED.last_error, updated_at=NOW()""",
                    source.code, source.discovery_url, error_label[:1000],
                )
                continue
            snapshot_checksum = hashlib.sha256(
                "\n".join(f"{a.url}|{a.checksum}" for a in artifacts).encode("utf-8")
            ).hexdigest()
            previous_snapshot = await conn.fetchval(
                "SELECT content_checksum FROM legal_source_snapshots WHERE source_code=$1", source.code
            )
            stats["sources_succeeded"] += 1
            stats["artifacts_seen"] += len(artifacts)
            source_events = 0

            async with conn.transaction():
                for artifact in artifacts:
                    existing = await conn.fetchrow(
                        """SELECT artifact_id, content_checksum, observation_count,
                                  consecutive_observation_count, auto_validated_at
                           FROM legal_source_artifacts
                           WHERE source_code=$1 AND artifact_url=$2""",
                        source.code, artifact.url,
                    )
                    corpus_id = await conn.fetchval(
                        "SELECT id FROM legal_corpus WHERE source_url=$1 OR source_pdf_url=$1 LIMIT 1",
                        artifact.url,
                    )
                    state = "BASELINED" if corpus_id else "NEW"
                    event_type = None
                    if not existing and not corpus_id:
                        event_type = "NEW_DOCUMENT"
                    elif existing and existing["content_checksum"] != artifact.checksum:
                        event_type = "DOCUMENT_METADATA_CHANGED"
                        state = "CHANGED"

                    artifact_id = existing["artifact_id"] if existing else f"artifact_{uuid4().hex[:18]}"
                    observed = await conn.fetchrow(
                        """INSERT INTO legal_source_artifacts
                           (artifact_id,source_code,artifact_url,title,corpus,legal_date,date_precision,
                            content_checksum,state,linked_corpus_id,last_changed_at,last_observed_run_id)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::varchar,$10,
                                   CASE WHEN $9::varchar='CHANGED' THEN NOW() ELSE NULL END,$11)
                           ON CONFLICT (source_code,artifact_url) DO UPDATE SET
                           title=EXCLUDED.title, legal_date=EXCLUDED.legal_date,
                           date_precision=EXCLUDED.date_precision, content_checksum=EXCLUDED.content_checksum,
                           state=EXCLUDED.state, linked_corpus_id=COALESCE(EXCLUDED.linked_corpus_id,legal_source_artifacts.linked_corpus_id),
                           observation_count=CASE WHEN legal_source_artifacts.last_observed_run_id IS DISTINCT FROM $11::varchar
                                                  THEN legal_source_artifacts.observation_count+1 ELSE legal_source_artifacts.observation_count END,
                           consecutive_observation_count=CASE
                               WHEN legal_source_artifacts.content_checksum<>EXCLUDED.content_checksum THEN 1
                               WHEN legal_source_artifacts.last_observed_run_id IS DISTINCT FROM $11::varchar
                                   THEN legal_source_artifacts.consecutive_observation_count+1
                               ELSE legal_source_artifacts.consecutive_observation_count END,
                           last_observed_run_id=$11::varchar, last_seen_at=NOW(),
                           auto_validated_at=CASE WHEN legal_source_artifacts.content_checksum<>EXCLUDED.content_checksum THEN NULL ELSE legal_source_artifacts.auto_validated_at END,
                           last_changed_at=CASE WHEN legal_source_artifacts.content_checksum<>EXCLUDED.content_checksum THEN NOW() ELSE legal_source_artifacts.last_changed_at END
                           RETURNING observation_count,consecutive_observation_count,auto_validated_at""",
                        artifact_id, source.code, artifact.url, artifact.title, artifact.corpus,
                        artifact.legal_date, artifact.date_precision, artifact.checksum, state, corpus_id,
                        run_id,
                    )
                    inserted = None
                    if event_type:
                        event_id = f"event_{uuid4().hex[:20]}"
                        inserted = await conn.fetchval(
                            """INSERT INTO legal_watch_events
                           (event_id,run_id,source_code,event_type,artifact_url,title,corpus,
                            legal_date,content_checksum,linked_corpus_id,payload)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
                           ON CONFLICT (source_code,artifact_url,content_checksum) DO NOTHING
                           RETURNING event_id""",
                        event_id, run_id, source.code, event_type, artifact.url, artifact.title,
                        artifact.corpus, artifact.legal_date, artifact.checksum, corpus_id,
                        json.dumps({"date_precision": artifact.date_precision}),
                        )
                        if inserted:
                            source_events += 1
                            stats["events_created"] += 1

                    score, reasons = score_artifact_validation(
                        artifact, int(observed["consecutive_observation_count"])
                    )
                    await conn.execute(
                        """UPDATE legal_source_artifacts SET validation_score=$3,
                           validation_reasons=$4::jsonb WHERE source_code=$1 AND artifact_url=$2""",
                        source.code, artifact.url, score, json.dumps(reasons),
                    )
                    if score < 85 or observed["auto_validated_at"]:
                        continue
                    pending_events = await conn.fetch(
                        """SELECT event_id FROM legal_watch_events
                           WHERE source_code=$1 AND artifact_url=$2 AND content_checksum=$3::char(64)
                             AND review_status='PENDING'""",
                        source.code, artifact.url, artifact.checksum,
                    )
                    if not pending_events:
                        continue
                    if not corpus_id:
                        document_type = source.document_type or (
                            "decision_crca" if artifact.corpus == "cima" else "arret_ccja"
                        )
                        official_reference = extract_official_reference(artifact.title)
                        change_type = infer_change_type(artifact.title)
                        corpus_id = await conn.fetchval(
                            """INSERT INTO legal_corpus
                               (ref,type,corpus,juridiction,titre,date_decision,source_url,
                                source_code,source_tier,source_verified_at,editorial_status,
                                impact_level,detected_at,official_identifier,official_citation,
                                change_type,metadata)
                               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'OFFICIAL',NOW(),
                                       'SOURCE_VERIFIED','TO_QUALIFY',NOW(),$9,$10,$11,$12::jsonb)
                               RETURNING id""",
                            official_reference or artifact.title[:200], document_type, artifact.corpus,
                            ("CRCA" if artifact.corpus == "cima" else
                             "CCJA" if artifact.corpus == "ohada" else source.name),
                            artifact.title, artifact.legal_date, artifact.url, source.code,
                            official_reference, official_reference, change_type,
                            json.dumps({
                                "automated_validation": True,
                                "validation_score": score,
                                "validation_reasons": reasons,
                                "date_precision": artifact.date_precision,
                            }),
                        )
                        if source.country_code or source.jurisdiction_code:
                            await conn.execute(
                                """UPDATE legal_corpus SET country_code=$2,
                                   jurisdiction_code=$3 WHERE id=$1""",
                                corpus_id, source.country_code, source.jurisdiction_code,
                            )
                    await conn.execute(
                        """UPDATE legal_source_artifacts SET state='AUTO_VALIDATED',
                           linked_corpus_id=$3,validation_score=$4,validation_reasons=$5::jsonb,
                           auto_validated_at=NOW() WHERE source_code=$1 AND artifact_url=$2""",
                        source.code, artifact.url, corpus_id, score, json.dumps(reasons),
                    )
                    for pending_event in pending_events:
                        event_id = pending_event["event_id"]
                        await conn.execute(
                            """UPDATE legal_watch_events SET review_status='AUTO_VALIDATED',
                               reviewed_at=NOW(),auto_validated_at=NOW(),linked_corpus_id=$2,
                               validation_score=$3,validation_reasons=$4::jsonb WHERE event_id=$1""",
                            event_id, corpus_id, score, json.dumps(reasons),
                        )
                        stats["events_auto_validated"] += 1
                        for watch in watches:
                            if not watch_matches_artifact(watch, artifact):
                                continue
                            delivery_status = "PENDING" if watch.get("email_enabled") else "DISABLED"
                            matched = await conn.fetchval(
                                """INSERT INTO legal_watch_matches
                                   (match_id,watch_id,event_id,workspace_id,delivery_status)
                                   VALUES ($1,$2,$3,$4,$5)
                                   ON CONFLICT (watch_id,event_id) DO NOTHING RETURNING match_id""",
                                f"match_{uuid4().hex[:20]}", watch["watch_id"], event_id,
                                watch["workspace_id"], delivery_status,
                            )
                            if matched:
                                stats["matches_created"] += 1
                                await conn.execute(
                                    """UPDATE legal_watch_subscriptions SET last_match_at=NOW(),
                                       last_match_count=last_match_count+1,last_evaluated_at=NOW(),
                                       delivery_status=$2,updated_at=NOW() WHERE watch_id=$1""",
                                    watch["watch_id"], delivery_status,
                                )

                await conn.execute(
                    """INSERT INTO legal_source_snapshots
                       (source_code,discovery_url,content_checksum,last_checked_at,last_changed_at,
                        last_status,last_error,artifact_count)
                       VALUES ($1,$2,$3::char(64),NOW(),CASE WHEN $4::char(64) IS DISTINCT FROM $3::char(64) THEN NOW() ELSE NULL END,
                               'SUCCESS',NULL,$5)
                       ON CONFLICT (source_code) DO UPDATE SET discovery_url=EXCLUDED.discovery_url,
                       content_checksum=EXCLUDED.content_checksum,last_checked_at=NOW(),
                       last_changed_at=CASE WHEN legal_source_snapshots.content_checksum IS DISTINCT FROM EXCLUDED.content_checksum THEN NOW() ELSE legal_source_snapshots.last_changed_at END,
                       last_status='SUCCESS',last_error=NULL,artifact_count=EXCLUDED.artifact_count,updated_at=NOW()""",
                    source.code, effective_url, snapshot_checksum, previous_snapshot, len(artifacts),
                )
            stats["sources"].append({"code": source.code, "status": "SUCCESS", "url": effective_url,
                                     "fallback_used": effective_url.rstrip("/") != source.discovery_url.rstrip("/"),
                                     "fetch_warnings": fetch_warnings, "artifacts": len(artifacts), "events": source_events})

        await conn.execute("UPDATE legal_watch_subscriptions SET last_evaluated_at=NOW() WHERE active=TRUE")
        if settings.watch_email_delivery_enabled:
            deliveries = await conn.fetch(
                """SELECT m.match_id,s.name AS watch_name,w.data->>'email' AS recipient,
                          e.title,e.source_code,e.artifact_url,e.validation_score
                   FROM legal_watch_matches m
                   JOIN legal_watch_subscriptions s ON s.watch_id=m.watch_id
                   JOIN legal_watch_events e ON e.event_id=m.event_id
                   LEFT JOIN account_workspaces w ON w.workspace_id=m.workspace_id
                   WHERE m.delivery_status='PENDING' AND s.active=TRUE
                     AND s.email_enabled=TRUE AND e.review_status='AUTO_VALIDATED'
                   ORDER BY m.matched_at LIMIT 100"""
            )
            for delivery in deliveries:
                claimed = await conn.fetchval(
                    """UPDATE legal_watch_matches SET delivery_status='SENDING'
                       WHERE match_id=$1 AND delivery_status='PENDING' RETURNING match_id""",
                    delivery["match_id"],
                )
                if not claimed:
                    continue
                recipient = str(delivery["recipient"] or "").strip()
                sent = await notify_legal_watch_alert(
                    recipient, delivery["watch_name"], dict(delivery)
                ) if recipient else False
                await conn.execute(
                    """UPDATE legal_watch_matches SET delivery_status=$2,
                       delivered_at=CASE WHEN $2::varchar='SENT' THEN NOW() ELSE NULL END,
                       delivery_error=CASE WHEN $2::varchar='FAILED' THEN $3 ELSE NULL END
                       WHERE match_id=$1""",
                    delivery["match_id"], "SENT" if sent else "FAILED",
                    None if sent else "Envoi indisponible ou destinataire absent",
                )
                if sent:
                    stats["emails_sent"] += 1
        stats["status"] = "PARTIAL" if stats["sources_failed"] else "SUCCESS"
        await conn.execute(
            """UPDATE legal_watch_runs SET status=$2,finished_at=NOW(),sources_succeeded=$3,
               sources_failed=$4,artifacts_seen=$5,events_created=$6,matches_created=$7,
               events_auto_validated=$8,emails_sent=$9,details=$10::jsonb
               WHERE run_id=$1""",
            run_id, stats["status"], stats["sources_succeeded"], stats["sources_failed"],
            stats["artifacts_seen"], stats["events_created"], stats["matches_created"],
            stats["events_auto_validated"], stats["emails_sent"],
            json.dumps({"sources": stats["sources"]}),
        )
        return stats
    except Exception as exc:
        stats["status"] = "FAILED"
        stats["error"] = str(exc)[:500]
        try:
            await conn.execute(
                "UPDATE legal_watch_runs SET status='FAILED',finished_at=NOW(),error_summary=$2 WHERE run_id=$1",
                run_id, str(exc)[:2000],
            )
        except Exception:
            pass
        raise
    finally:
        if lock_acquired:
            await conn.execute("SELECT pg_advisory_unlock($1)", 7240202601)
        await conn.close()
