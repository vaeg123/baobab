# Baobab Sources — fondation 0.5

Baobab Sources organise la chaîne d'acquisition, de vérification, de versionnement et de publication du droit. Il ne remplace pas encore `legal_corpus` : il en devient progressivement la couche canonique et traçable.

## Principes

1. La disponibilité publique d'un document ne vaut pas autorisation de reproduction ou d'analyse.
2. Le fichier original, son empreinte et son canal de réception sont conservés séparément du texte normalisé.
3. Une source officielle, une analyse éditoriale, une synthèse automatique et un document privé sont des objets distincts.
4. Une relation juridique forte conserve sa preuve, son niveau de confiance et son statut de validation.
5. `legal_corpus` reste la projection de compatibilité utilisée par la recherche et l'API AvocAssist pendant la migration.

## Modèle

- `legal_sources` : institution, canal, convention, licence, droits, fréquence et couverture.
- `legal_documents` : identité juridique canonique et projection du document courant.
- `legal_document_versions` : versions et périodes d'applicabilité.
- `legal_source_acquisitions` : journal de réception, intégrité, droits et transformations.
- `legal_editorial_reviews` : décisions de validation humaine.
- `legal_knowledge_relations` : modification, abrogation, application, interprétation, citation ou revirement.
- `legal_corpus_audit_runs` : résultats horodatés des audits de couverture et de qualité.

Les tables existantes `legal_provisions` et `legal_document_relations` demeurent disponibles. Elles seront migrées vers les identifiants canoniques après qualification des documents parents.

## API initiale

Les routes sont réservées au superadministrateur :

- `GET /api/v1/sources/overview`
- `GET /api/v1/sources`
- `PATCH /api/v1/sources/{source_code}`
- `POST /api/v1/institution/documents`
- `GET /api/v1/sources/audits/latest`

Le dépôt institutionnel enregistre les métadonnées, l'empreinte et l'URI sécurisée du fichier. Le transfert binaire signé et les comptes institutionnels dédiés constituent le lot suivant.

## Procédures opérationnelles

```bash
# Appliquer uniquement la migration 014 et projeter le corpus existant
python -m baobab.pipeline.apply_sources_foundation

# Produire un audit en lecture seule
python -m baobab.pipeline.audit_corpus_foundation

# Calculer les empreintes des textes normalisés manquantes
python -m baobab.pipeline.backfill_corpus_checksums
```

## État du premier audit

- 3 884 documents examinés ;
- 2 803 documents avec titre et texte exploitables ;
- 1 081 documents incomplets ;
- 20 doublons potentiels par URL ;
- 11 documents sans URL source ;
- 2 803 textes normalisés dotés d'une empreinte SHA-256 ;
- droits documentaires à régulariser pour l'ensemble des imports historiques.

Ces chiffres constituent un état de travail, pas une déclaration publique de couverture juridique.

## Prochain lot

1. interface superadmin « Sources et qualité » ;
2. qualification des 20 doublons potentiels ;
3. rattachement des 47 documents non mappés ;
4. registre des originaux et stockage immuable ;
5. comptes institutionnels avec permissions limitées ;
6. dépôt de lots et rapport d'intégration ;
7. workflow éditorial à deux niveaux ;
8. migration des articles et relations vers les identifiants canoniques.
