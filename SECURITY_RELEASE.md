# Correctifs de sécurité — 19 septembre 2026

Les identités client et administrateur conservent des mots de passe distincts. Les réponses de workspace utilisent une liste explicite de champs publics. Les anciens codes permanents ne permettent plus l'authentification : des sessions individuelles expirent après huit heures et seule leur empreinte est enregistrée. Un changement de mot de passe invalide les sessions de l'identité concernée ; déconnexion et suspension sont contrôlées.

## Publication

- Installer Python 3.12 et les versions avec empreintes de `requirements.txt`. Le manifeste Python et Stripe sont alignés. Les outils de numérisation disposent de `requirements-ocr.txt` séparé.
- Les sources des verrouillages sont `requirements.in` et `requirements-ocr.in`. Régénération : `python -m uv pip compile requirements.in --universal --python-version 3.12 --generate-hashes --output-file requirements.txt`.
- La première utilisation des sessions crée la table `account_sessions` et son index d'expiration, selon le mécanisme d'initialisation déjà utilisé par l'application. Vérifier le droit de création ou provisionner ces objets avant publication.
- Déployer le backend et son interface statique ensemble. Prévoir une reconnexion avec email et mot de passe ; ne pas redistribuer les anciens codes permanents.
- PostgreSQL doit être le stockage de production. Le mode en mémoire reste réservé au développement et aux tests.

## Vérifications locales

235 tests réussis, 5 tests d'intégration ignorés dans la suite sans services externes. Le test PostgreSQL dédié a ensuite été exécuté avec succès : persistance sans état mémoire, empreinte seule en base, expiration, déconnexion, changement de mot de passe client sans modification de celui de l'administrateur.

L'audit des dépendances de production verrouillées ne signale aucune vulnérabilité connue. Le workflow `.github/workflows/security.yml` vérifie les tests et ces versions. La recette Python a été exécutée sous Python 3.14 ; le verrouillage universel cible également Python 3.12 et le workflow vérifiera cette version sur Linux.

La version effectivement installée sur le serveur et la publication restent à contrôler séparément.
