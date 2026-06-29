# BAOBAB — Architecture

## Vue d'ensemble : 10 couches

```
┌─────────────────────────────────────────────────────────────┐
│  10. Interface utilisateur (Dashboard, Alertes, API)        │
├─────────────────────────────────────────────────────────────┤
│   9. API Gateway (FastAPI, Auth, Rate Limiting)             │
├─────────────────────────────────────────────────────────────┤
│   8. Vertical Products (CIMA, OHADA, BCEAO, Fiscal, RH)    │
├─────────────────────────────────────────────────────────────┤
│   7. Compliance Engine (score, rapport, audit trail)        │
├─────────────────────────────────────────────────────────────┤
│   6. Risk Engine (probabilité × gravité × urgence)          │
├─────────────────────────────────────────────────────────────┤
│   5. Reasoning Engine (LLM guidé, raisonnement tracé)       │
├─────────────────────────────────────────────────────────────┤
│   4. Legal Event Engine (cascade, délais, obligations)      │
├─────────────────────────────────────────────────────────────┤
│   3. Digital Legal Twin (entité + obligations + historique) │
├─────────────────────────────────────────────────────────────┤
│   2. Legal Graph (Neo4j — nœuds, arêtes, relations)        │
├─────────────────────────────────────────────────────────────┤
│   1. Legal Knowledge Fabric (Legal Atoms — immuables)       │
└─────────────────────────────────────────────────────────────┘
```

## Couche 1 — Legal Knowledge Fabric

Socle immuable. Chaque disposition juridique est un **Legal Atom** :
- Identifiant permanent : `CI.CIMA.CODE.ART260.V2022`
- Texte source + territoire + corpus + version
- Vecteur sémantique (pgvector 1536 dims)
- Jamais modifié — toute évolution crée un nouvel atom

## Couche 2 — Legal Graph (Neo4j)

Graphe orienté typé :
- Nœuds : LegalAtom, LegalEntity, LegalRule, LegalProcess
- Arêtes : `abrogated_by`, `triggers`, `applies_to`, `cites`, `sanctions`
- Requêtes Cypher pour traversée de dépendances juridiques

## Couche 3 — Digital Legal Twin

Jumeau numérique de chaque entité assujettie :
- Obligations actives
- Historique de conformité
- Score de risque
- Lié au Legal Graph (Neo4j) + store relationnel (PostgreSQL)

## Couche 4 — Legal Event Engine

Moteur d'événements juridiques :
- Reçoit un `LegalEvent` (ex : `SINISTRE_INCENDIE`)
- Déclenche la `CascadeDefinition` enregistrée
- Calcule tous les `ProcessStep` avec dates d'échéance
- Produit un `LegalProcess` complet

## Couches 5-6 — Reasoning + Risk Engine

- **Reasoning** : raisonnement tracé, sources primaires, exceptions
- **Risk** : score composite `probabilité × gravité × urgence`

## Couches 7-10 — Compliance, Verticals, API, UI

- **Compliance** : score 0–1, statuts COMPLIANT / AT_RISK / NON_COMPLIANT
- **Verticals** : CIMA (MVP), OHADA, BCEAO, Fiscal, RH, Banque
- **API** : FastAPI REST + OpenAPI docs
- **UI** : Dashboard alertes + Digital Twin viewer (phase 2)

## Flux de données principal

```
Document juridique
      ↓
Pipeline Ingestion → Extraction → Classification → Atomisation
      ↓
Legal Atom stocké (PostgreSQL + pgvector + Neo4j)
      ↓
Événement client (ex: sinistre incendie)
      ↓
Legal Event Engine → CascadeEngine → LegalProcess (7 étapes)
      ↓
Compliance Engine → Score + Statut
      ↓
Alert Generator → Alertes prioritisées
      ↓
API Response → Client
```
