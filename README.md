# BAOBAB

**La plateforme internationale d'intelligence juridique**

BAOBAB transforme le droit français, européen, africain et international en intelligence opérationnelle, sourcée et traçable.

Son expertise historique en OHADA, CIMA, BCEAO et UEMOA reste un avantage central. La plateforme accueille désormais des packs juridictionnels indépendants, à commencer par la France, l'Union européenne et la CEDH.

---

## Le paradigme

Les plateformes actuelles répondent à : **Où trouver l'information ?**

BAOBAB répond à : **Que dois-je faire maintenant ?**

---

## Architecture — La métaphore du baobab

| Niveau | Composant | Rôle |
|--------|-----------|------|
| Racines | Legal Knowledge Fabric | France, UE, CEDH, OHADA, CIMA, BCEAO, UEMOA — invisible, profond, permanent |
| Tronc | Core Engine | Legal Event Engine + Reasoning Engine |
| Branches | Packs et produits verticaux | France, Europe, CEDH, CIMA, OHADA, BCEAO, Fiscalité, Travail, Banque |
| Fruits | Outputs décisionnels | Alertes, scores, simulations, recommandations |
| Feuilles | Legal Atoms | Unités minimales — `CI.OHADA.AUSCGIE.ART247.V2024` |

---

## MVP — BAOBAB CIMA Module Sinistre

Premier vertical : assurance CIMA Côte d'Ivoire.

```bash
POST /api/v1/cima/sinistre
{
  "entity_id": "compagnie-001",
  "sinistre_type": "SINISTRE_INCENDIE",
  "occurred_at": "2024-06-01T00:00:00Z"
}
```

Réponse : cascade complète calculée, délais CIMA, score de conformité, alertes.

**Objectif mesurable** : réduction du délai moyen de traitement sinistre de 40 jours à 18 jours.

## Pack France et socle international

- **France** : connecteurs officiels Légifrance et Judilibre via PISTE.
- **Union européenne** : registre EUR-Lex/CELLAR pour les textes et la jurisprudence.
- **CEDH** : registre HUDOC pour les arrêts, décisions et avis consultatifs.
- **International** : modèle commun de juridictions, sources, langues, citations et dates d'applicabilité.

```bash
GET  /api/v1/legal/jurisdictions
GET  /api/v1/legal/sources
POST /api/v1/legal/search
{
  "query": "responsabilité du fait des produits",
  "jurisdiction_code": "FR",
  "country_code": "FR",
  "language_code": "fr",
  "as_of": "2026-08-25"
}
```

Une source étrangère n'est jamais présentée comme directement applicable sans indication de son autorité dans la juridiction demandée.

---

## Stack technique

- **FastAPI** — API REST
- **PostgreSQL + pgvector** — données transactionnelles + recherche vectorielle
- **Neo4j** — Legal Graph (nœuds et arêtes typées)
- **SQLAlchemy + Alembic** — ORM async + migrations
- **Docker Compose** — environnement local

---

## Démarrage rapide

```bash
# 1. Infrastructure
docker compose up -d

# 2. Dépendances
pip install -e ".[dev]"

# 3. API
uvicorn baobab.api.main:app --reload

# 4. Tests
pytest
```

API disponible sur http://localhost:8000/api/docs

---

## Structure du projet

```
baobab/
├── baobab/
│   ├── core/           # CLDM + Legal Atoms + modèles
│   ├── engines/        # Event, Reasoning, Compliance, Risk
│   ├── verticals/      # CIMA (MVP), OHADA, BCEAO...
│   ├── pipeline/       # Ingestion documentaire
│   ├── api/            # FastAPI routes
│   └── db/             # PostgreSQL + migrations
├── docs/               # Architecture, invariants, roadmap
└── tests/
```

---

## Invariants

1. Toute connaissance juridique est immuable et versionnée.
2. Toute conclusion est explicable et traçable.
3. Les données d'un client n'alimentent jamais un modèle concurrent.
4. Toute obligation est rattachée à une source juridique primaire.
5. BAOBAB produit du raisonnement. La décision appartient à l'humain.

---

## Roadmap

| Période | Phase |
|---------|-------|
| M1–M6 | MVP CIMA Sinistre — 3 pilotes Côte d'Ivoire |
| M7–M12 | CIMA complet — 10 clients — Digital Twin |
| M13–M18 | Pack France : Légifrance, Judilibre, veille et citations |
| M19–M24 | Union européenne + CEDH + relations France–Europe |
| M25–M36 | Nouveaux packs nationaux et droit international |

---

*BAOBAB — Document confidentiel — v0.1.0 — 2026*
