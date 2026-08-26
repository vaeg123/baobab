"""Moteur prudent de détection des nouveautés sur les sources juridiques officielles."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from baobab.api.routes.legal import _conn


@dataclass(frozen=True)
class WatchSource:
    code: str
    name: str
    corpus: str
    discovery_url: str
    parser: str


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
    written = re.search(r"\b(\d{1,2})\s+([a-zéûôîàèùç]+)\s+(20\d{2})\b", normalized)
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
    return sorted(artifacts.values(), key=lambda item: item.url)


def parse_source(html: str, source: WatchSource) -> list[Artifact]:
    parsers = {"ohada_biblio": parse_ohada_biblio, "cima_crca": parse_cima_crca}
    return parsers[source.parser](html, source)


def watch_matches_artifact(watch: dict, artifact: Artifact) -> bool:
    corpus = str(watch.get("corpus") or "all").lower()
    corpus_aliases = {
        "ohada": {"ohada", "ccja"}, "cima": {"cima", "crca"},
        "bceao": {"bceao", "uemoa"}, "bceao_uemoa": {"bceao", "uemoa"},
    }
    if corpus != "all" and artifact.corpus not in corpus_aliases.get(corpus, {corpus}):
        return False
    query = str(watch.get("query") or "").strip().lower()
    if not query:
        return True
    terms = [term.strip() for term in re.split(r"[,;]", query) if term.strip()]
    haystack = f"{artifact.title} {artifact.url}".lower()
    return any(term in haystack for term in terms)


async def _fetch_source(client: httpx.AsyncClient, source: WatchSource) -> tuple[WatchSource, str]:
    response = await client.get(
        source.discovery_url,
        headers={
            "User-Agent": "BAOBAB-Legal-Watch/1.0 (+https://vaegbaobab.com)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
    )
    response.raise_for_status()
    return source, response.text


async def run_watch_cycle(trigger: str = "manual") -> dict:
    """Exécute un cycle idempotent, journalisé et protégé contre le chevauchement."""
    run_id = f"run_{uuid4().hex[:20]}"
    conn = await _conn()
    lock_acquired = False
    stats = {
        "run_id": run_id, "trigger": trigger, "status": "RUNNING",
        "sources_checked": len(WATCH_SOURCES), "sources_succeeded": 0,
        "sources_failed": 0, "artifacts_seen": 0, "events_created": 0,
        "matches_created": 0, "sources": [],
    }
    try:
        lock_acquired = bool(await conn.fetchval("SELECT pg_try_advisory_lock($1)", 7240202601))
        if not lock_acquired:
            return {**stats, "status": "SKIPPED_ALREADY_RUNNING"}
        await conn.execute(
            "INSERT INTO legal_watch_runs (run_id, trigger, status, sources_checked) VALUES ($1,$2,'RUNNING',$3)",
            run_id, trigger, len(WATCH_SOURCES),
        )
        timeout = httpx.Timeout(15.0, connect=8.0)
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

            _, html = result
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
                        "SELECT artifact_id, content_checksum FROM legal_source_artifacts WHERE source_code=$1 AND artifact_url=$2",
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
                    await conn.execute(
                        """INSERT INTO legal_source_artifacts
                           (artifact_id,source_code,artifact_url,title,corpus,legal_date,date_precision,
                            content_checksum,state,linked_corpus_id,last_changed_at)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::varchar,$10,CASE WHEN $9::varchar='CHANGED' THEN NOW() ELSE NULL END)
                           ON CONFLICT (source_code,artifact_url) DO UPDATE SET
                           title=EXCLUDED.title, legal_date=EXCLUDED.legal_date,
                           date_precision=EXCLUDED.date_precision, content_checksum=EXCLUDED.content_checksum,
                           state=EXCLUDED.state, linked_corpus_id=COALESCE(EXCLUDED.linked_corpus_id,legal_source_artifacts.linked_corpus_id),
                           last_seen_at=NOW(), last_changed_at=CASE WHEN legal_source_artifacts.content_checksum<>EXCLUDED.content_checksum THEN NOW() ELSE legal_source_artifacts.last_changed_at END""",
                        artifact_id, source.code, artifact.url, artifact.title, artifact.corpus,
                        artifact.legal_date, artifact.date_precision, artifact.checksum, state, corpus_id,
                    )
                    if not event_type:
                        continue
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
                    if not inserted:
                        continue
                    source_events += 1
                    stats["events_created"] += 1
                    for watch in watches:
                        if not watch_matches_artifact(watch, artifact):
                            continue
                        matched = await conn.fetchval(
                            """INSERT INTO legal_watch_matches
                               (match_id,watch_id,event_id,workspace_id,delivery_status)
                               VALUES ($1,$2,$3,$4,'DISABLED')
                               ON CONFLICT (watch_id,event_id) DO NOTHING RETURNING match_id""",
                            f"match_{uuid4().hex[:20]}", watch["watch_id"], inserted,
                            watch["workspace_id"],
                        )
                        if matched:
                            stats["matches_created"] += 1
                            await conn.execute(
                                """UPDATE legal_watch_subscriptions SET last_match_at=NOW(),
                                   last_match_count=last_match_count+1, last_evaluated_at=NOW(),
                                   delivery_status='DISABLED', updated_at=NOW() WHERE watch_id=$1""",
                                watch["watch_id"],
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
                    source.code, source.discovery_url, snapshot_checksum, previous_snapshot, len(artifacts),
                )
            stats["sources"].append({"code": source.code, "status": "SUCCESS", "artifacts": len(artifacts), "events": source_events})

        await conn.execute("UPDATE legal_watch_subscriptions SET last_evaluated_at=NOW() WHERE active=TRUE")
        stats["status"] = "PARTIAL" if stats["sources_failed"] else "SUCCESS"
        await conn.execute(
            """UPDATE legal_watch_runs SET status=$2,finished_at=NOW(),sources_succeeded=$3,
               sources_failed=$4,artifacts_seen=$5,events_created=$6,matches_created=$7,details=$8::jsonb
               WHERE run_id=$1""",
            run_id, stats["status"], stats["sources_succeeded"], stats["sources_failed"],
            stats["artifacts_seen"], stats["events_created"], stats["matches_created"],
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
