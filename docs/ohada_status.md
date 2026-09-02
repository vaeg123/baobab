# État du chantier OHADA

Dernière actualisation : 1er septembre 2026.

## Ce qui fait autorité dans le dépôt

- `data/raw/ohada_actes/*.pdf` ne contient pas les Actes uniformes : ces fichiers sont des impressions de pages du site `ohada.com`. Ils ne doivent être ni OCRisés comme textes juridiques, ni injectés en base.
- Les textes opérationnels sont stockés dans `legal_corpus.texte_integral` avec leur URL source.
- `python -m baobab.pipeline.materialize_ohada_texts` exporte ces textes dans `data/processed/ohada_texts/` et produit un manifeste avec empreinte SHA-256, provenance et métriques de qualité.
- Un texte exporté reste au statut `AUTOMATED_TO_REVIEW`. L'extraction automatisée ne vaut pas validation éditoriale.

## État mesuré avant la reprise

- 2 628 décisions OHADA/CCJA issues de la plateforme officielle ;
- 2 589 décisions avec texte intégral ;
- 45 documents du lot d'archives local tous présents avec texte ;
- 36 notices sans texte mais avec un PDF récupérable ;
- 492 notices sans PDF officiel identifié.

## Reprendre le pipeline

```bash
python -m baobab.pipeline.verify_ohada_arrets
python -m baobab.pipeline.backfill_ohada_texts
python -m baobab.pipeline.materialize_ohada_texts
# Rafraîchissement contrôlé d'un Acte depuis sa copie institutionnelle :
python -m baobab.pipeline.refresh_ohada_act AUSCGIE-2014
python -m baobab.pipeline.refresh_ohada_act AUSCGIE-2014 --apply
python -m baobab.pipeline.build_ohada_provisions --apply
python -m baobab.pipeline.link_ohada_case_law --apply
python -m pytest -q tests/test_ohada_provisions.py tests/test_ohada_case_links.py
```

Toujours exécuter sans `--apply` en premier pour contrôler les volumes. Les liens ne sont créés que pour une citation textuelle explicite et pour la version temporellement applicable de l'Acte.

## Temporalité et limites

Le catalogue `baobab/pipeline/ohada_catalog.py` centralise les alias, familles de versions, bornes d'effet confirmées et sources institutionnelles. Une date inconnue reste inconnue : ne jamais la déduire de la seule année de la référence.

La couverture est volontairement annoncée comme partielle tant que les articles n'ont pas été rapprochés du Journal officiel et validés par un juriste.

### Anomalie connue

L'enregistrement `AUCTMR-2003` porte actuellement en base le texte de l'ancien Acte uniforme sur les sûretés. Le contrôle d'identité l'exclut automatiquement de la construction des articles. Il faut retrouver le Journal officiel authentique du texte sur le transport avant de remplacer cet enregistrement.

La tentative de rattrapage du 1er septembre 2026 a examiné 39 décisions sans texte : 31 notices officielles ont refusé le téléchargement, 4 réponses n'étaient pas des PDF, 3 notices n'exposaient aucun PDF et 1 PDF image requiert l'OCR. Aucun texte douteux n'a été injecté.

## Résultat appliqué le 1er septembre 2026

- 8 textes d'Actes matérialisés en UTF-8 avec manifeste et empreintes ;
- 7 textes acceptés par le contrôle d'identité, `AUCTMR-2003` rejeté ;
- 1 477 articles reconstruits en base avec statut `AUTOMATED_PARTIAL_SOURCE` ;
- 576 liens de citations explicites créés sur 2 589 décisions textuelles ;
- aucune validation humaine revendiquée (`human_reviewed=false`).

L'AUSCGIE-2014 a été remplacé le 2 septembre 2026 par le texte complet de la copie institutionnelle `explnum_id=2032` : 240 pages, 599 967 caractères, 906 articles uniques détectés jusqu'à l'article 920. L'empreinte du PDF et la méthode d'extraction sont conservées dans les métadonnées et le manifeste.

Les cinq références OHADA utilisées par la cascade « Création SARL » sont désormais consultables : AUSCGIE 260, 309 et 311 ; AUDCG 25 et 27.

## Circuit de validation éditoriale (2 septembre 2026)

La migration `021_ohada_provision_reviews.sql` ajoute un journal append-only des décisions prises sur chaque article. Le superadmin dispose, dans « Sources & qualité », d'une file « Articles OHADA à relire » avec quatre états :

- `IN_REVIEW` : article pris en relecture ;
- `DOCUMENT_VERIFIED` : texte rapproché de la copie source, sans revendiquer une validation juridique ;
- `VALIDATED` : contenu relu et validé juridiquement par un humain identifié ;
- `REJECTED` : article écarté, avec motif obligatoire.

Chaque transition enregistre l'identité issue du jeton superadmin, la date et une note sans écraser l'historique. Le statut courant est répercuté sur `legal_provisions.verification_status` et affiché publiquement avec l'article. Ne jamais attribuer automatiquement `DOCUMENT_VERIFIED` ou `VALIDATED` lors d'une extraction ou d'une migration.

## Parcours juridique visuel (2 septembre 2026)

L'interface affiche désormais un « Parcours juridique OHADA » dès qu'un article ou une jurisprudence est présenté :

- l'article est placé entre publication, entrée en vigueur, décisions qui le citent et fin d'effet éventuelle ;
- chaque décision liée montre les étapes antérieures connues, la juridiction et la date de la décision, puis l'article examiné ;
- la fiche complète d'une décision présente un schéma procédural alimenté par la fiche jurisprudentielle structurée et les règles citées.

Une date ou une étape absente doit toujours porter la mention « non documentée ». Le client ne doit jamais déduire un degré de juridiction ou une date à partir du seul ordre narratif. Les liens article–décision restent qualifiés comme automatiques tant qu'ils ne sont pas validés éditorialement.
