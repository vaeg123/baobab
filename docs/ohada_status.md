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
- 713 articles reconstruits en base avec statut `AUTOMATED_PARTIAL_SOURCE` ;
- 516 liens de citations explicites créés sur 2 589 décisions textuelles ;
- aucune validation humaine revendiquée (`human_reviewed=false`).

Répartition des liens : AUPSRVE-1998 (333), AUDCG-2010 (141), AUSCGIE-2014 (32), AUS-2010 (8), AUDCIF-2017 (2). Aucun lien explicite détecté pour AUPCAP-2015 et AUSCOOP-2010.
