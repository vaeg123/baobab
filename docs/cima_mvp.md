# BAOBAB CIMA — MVP Module Sinistre

## Contexte

Le Code CIMA (Conférence Interafricaine des Marchés d'Assurances) régit l'assurance
dans 14 pays d'Afrique subsaharienne francophone.

Le non-respect des délais d'indemnisation expose les compagnies à :
- Des intérêts de retard au double du taux légal (Art. 270 CIMA)
- Des sanctions régulatoires de la CRCA
- Des risques de réputation importants

**Problème actuel** : délai moyen de traitement sinistre = 40 jours (objectif CIMA : 90j max)
**Objectif BAOBAB** : ramener à 18 jours par orchestration intelligente

---

## Cascades implémentées

### SINISTRE_INCENDIE (Art. 12, 260–270 CIMA)

| Étape | Délai | Sanction |
|-------|-------|---------|
| Déclaration sinistre | J+5 | Déchéance possible (Art. 12) |
| Désignation expert | J+15 | Mise en demeure assureur |
| Rapport d'expertise | J+30 | — |
| Offre provisionnelle | J+45 | Intérêts double taux légal |
| Offre définitive | J+90 | Intérêts double taux légal |
| Paiement indemnité | J+105 | Intérêts majorés |
| Archivage dossier | Sans délai fixe | — |

### SINISTRE_AUTO (Art. 231–252 CIMA)

| Étape | Délai | Sanction |
|-------|-------|---------|
| Déclaration | J+5 | — |
| Constat / PV | J+10 | — |
| Expertise véhicule | J+20 | — |
| Offre d'indemnisation | J+60 | Intérêts légaux (Art. 252) |
| Paiement | J+75 | — |

---

## API MVP

### Déclarer un sinistre

```http
POST /api/v1/cima/sinistre
Content-Type: application/json

{
  "entity_id": "compagnie-001",
  "sinistre_type": "SINISTRE_INCENDIE",
  "occurred_at": "2024-06-01T00:00:00Z",
  "metadata": {
    "police_number": "CI-2024-001234",
    "insured_name": "Société ABC SARL"
  }
}
```

### Réponse

```json
{
  "event_id": "uuid-...",
  "process_id": "proc-uuid-...",
  "steps": [
    {
      "step_id": "uuid-step-00",
      "name": "Déclaration sinistre",
      "status": "pending",
      "due_date": "2024-06-06T00:00:00",
      "deadline_days": 5
    }
  ],
  "compliance": {
    "score": 0.0,
    "status": "pending",
    "overdue_count": 0
  },
  "alerts": []
}
```

---

## Niveaux d'alerte

| Niveau | Déclencheur |
|--------|------------|
| `info` | Information neutre |
| `warning` | Échéance dans 6–15 jours |
| `critical` | Échéance dans 0–5 jours |
| `overdue` | Échéance dépassée |

---

## Scores de conformité

| Score | Statut | Signification |
|-------|--------|--------------|
| 0% complété, 0 overdue | `pending` | Processus démarré, pas d'action encore |
| ≥50% complété | `at_risk` | En cours, attention requise |
| ≥80% complété | `compliant` | Bonne progression |
| Overdue > 0 | `non_compliant` | Violation CIMA en cours |

---

## Prochaines étapes MVP

1. Persistance PostgreSQL des processus et événements
2. Webhook alertes (email / SMS / Slack)
3. Dashboard React temps réel
4. SINISTRE_RC et SINISTRE_CORPS
5. Module résiliation (Art. 12–20 CIMA)
