# BAOBAB — Roadmap 36 mois

## Phase 1 : MVP CIMA Sinistre (M1–M6)

**Objectif** : 3 compagnies pilotes en Côte d'Ivoire

### Livrables
- [ ] Module sinistre CIMA complet (incendie + auto)
- [ ] API REST documentée (FastAPI + OpenAPI)
- [ ] Cascade engine avec délais CIMA Art. 12, 231-252, 260-300
- [ ] Score de conformité temps réel
- [ ] Système d'alertes (info / warning / critical / overdue)
- [ ] Dashboard pilote (React)
- [ ] Intégration PostgreSQL + pgvector

**KPI** : réduction délai moyen traitement sinistre de 40j → 18j

---

## Phase 2 : CIMA Complet + Digital Twin (M7–M12)

**Objectif** : 10 clients — 500K FCFA ARR minimum

### Livrables
- [ ] Tous types de sinistres CIMA (RC, Corps, Maritime)
- [ ] Digital Legal Twin complet par entité
- [ ] Legal Graph Neo4j en production
- [ ] Module résiliation / renouvellement
- [ ] Pipeline ingestion documentaire automatisée
- [ ] API Tier 1 (accès clients directs)
- [ ] Module audit trail + export régulatoire

---

## Phase 3 : OHADA + Expansion Sénégal (M13–M18)

**Objectif** : couverture OHADA + 2ème marché

### Livrables
- [ ] BAOBAB OHADA : AUSCGIE, AUPC, AUS
- [ ] Expansion Sénégal (CIMA + OHADA)
- [ ] Reasoning Engine v1 (LLM guidé + Legal Atoms)
- [ ] Module M&A et restructuration
- [ ] Partenariat cabinet d'avocats (distribution)

---

## Phase 4 : API Economy (M19–M24)

**Objectif** : Tier 3 — intégration dans les ERP africains

### Livrables
- [ ] API Tier 3 public (pay-per-call)
- [ ] SDK Python + JavaScript
- [ ] Webhooks événements juridiques
- [ ] Marketplace Legal Atoms (monétisation corpus)
- [ ] Intégration ERP (SAP, Sage Africa, Odoo)

---

## Phase 5 : BCEAO + Institutionnel (M25–M36)

**Objectif** : couverture pan-africaine UEMOA

### Livrables
- [ ] BAOBAB BCEAO : réglementation bancaire UEMOA
- [ ] Module compliance bancaire (ratio prudentiels, KYC/AML)
- [ ] Contrats institutionnels (régulateurs, ministères)
- [ ] BAOBAB Fiscal (TVA, IS, droit douanier UEMOA)
- [ ] Expansion Cameroun, Mali, Burkina Faso

---

## Métriques cibles à M36

| Métrique | Cible |
|----------|-------|
| Clients actifs | 50+ |
| ARR | 500M FCFA (750K EUR) |
| Marchés | 5 pays UEMOA |
| Corpus juridiques | CIMA + OHADA + BCEAO + Fiscal |
| Legal Atoms indexés | 10 000+ |
| Uptime API | 99.9% |
