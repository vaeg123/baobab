"""Référentiel déterministe des versions d'Actes uniformes OHADA.

Les dates d'effet renseignées ici ne sont utilisées que lorsqu'elles ont été
confirmées par une publication institutionnelle. Une date absente ne doit pas
être inventée à partir de l'année figurant dans la référence.
"""

from __future__ import annotations

from datetime import date


ACTS = {
    "AUPSRVE-2023": {
        "family": "AUPSRVE",
        "aliases": ("AUPSRVE", "PROCEDURES SIMPLIFIEES DE RECOUVREMENT", "VOIES D EXECUTION"),
        "effective_from": date(2024, 2, 16),
        "identity_markers": ("PROCEDURES SIMPLIFIEES", "VOIES DEXECUTION"),
        "source": "https://www.ohada.org/organisation-des-procedures-simplifiees-de-recouvrement-et-des-voies-dexecution/",
    },
    "AUPSRVE-1998": {
        "family": "AUPSRVE",
        "aliases": ("AUPSRVE", "PROCEDURES SIMPLIFIEES DE RECOUVREMENT", "VOIES D EXECUTION"),
        "effective_until": date(2024, 2, 15),
        "identity_markers": ("PROCEDURES SIMPLIFIEES", "VOIES DEXECUTION"),
    },
    "AUSCGIE-2014": {
        "family": "AUSCGIE",
        "aliases": ("AUSCGIE", "SOCIETES COMMERCIALES ET DU GIE"),
        "effective_from": date(2014, 5, 5),
        "identity_markers": ("SOCIETES COMMERCIALES", "GROUPEMENT DINTERET ECONOMIQUE"),
        "source": "https://www.ohada.org/droit-des-societes-commerciales-et-du-gie/",
    },
    "AUSCGIE-1997": {
        "family": "AUSCGIE",
        "aliases": ("AUSCGIE", "SOCIETES COMMERCIALES ET DU GIE"),
        "effective_until": date(2014, 5, 4),
        "identity_markers": ("SOCIETES COMMERCIALES", "GROUPEMENT DINTERET ECONOMIQUE"),
    },
    "AUDCG-2010": {
        "family": "AUDCG",
        "aliases": ("AUDCG", "DROIT COMMERCIAL GENERAL"),
        "effective_from": date(2011, 5, 15),
        "source": "https://www.ohada.org/droit-commercial-general/",
    },
    "AUDCG-1997": {
        "family": "AUDCG",
        "aliases": ("AUDCG", "DROIT COMMERCIAL GENERAL"),
        "effective_until": date(2011, 5, 14),
    },
    "AUPCAP-2015": {
        "family": "AUPCAP",
        "aliases": ("AUPCAP", "PROCEDURES COLLECTIVES D APUREMENT DU PASSIF"),
        "identity_markers": ("PROCEDURES COLLECTIVES", "APUREMENT DU PASSIF"),
    },
    "AUPCAP-1998": {
        "family": "AUPCAP",
        "aliases": ("AUPCAP", "PROCEDURES COLLECTIVES D APUREMENT DU PASSIF"),
        "identity_markers": ("PROCEDURES COLLECTIVES", "APUREMENT DU PASSIF"),
    },
    "AUDCIF-2017": {
        "family": "AUDCIF",
        "aliases": ("AUDCIF", "DROIT COMPTABLE ET A L INFORMATION FINANCIERE", "SYSCOHADA"),
    },
    "AUS-2010": {
        "family": "AUS",
        "aliases": ("ACTE UNIFORME PORTANT ORGANISATION DES SURETES", "DROIT DES SURETES"),
        "identity_markers": ("SURETES",),
    },
    "AUS-1997": {
        "family": "AUS",
        "aliases": ("ACTE UNIFORME PORTANT ORGANISATION DES SURETES", "DROIT DES SURETES"),
        "identity_markers": ("SURETES",),
    },
    "AUSCOOP-2010": {
        "family": "AUSCOOP",
        "aliases": ("AUSCOOP", "SOCIETES COOPERATIVES"),
    },
    "AUCTMR-2003": {
        "family": "AUCTMR",
        "aliases": ("AUCTMR", "TRANSPORT DE MARCHANDISES PAR ROUTE"),
    },
    "AUA-2017": {"family": "AUA", "aliases": ("AUA", "DROIT DE L ARBITRAGE")},
    "AUA-1999": {"family": "AUA", "aliases": ("AUA", "DROIT DE L ARBITRAGE")},
    "AUM-2017": {"family": "AUM", "aliases": ("AUM", "DROIT DE LA MEDIATION")},
    "AUCE-2000": {"family": "AUCE", "aliases": ("AUCE", "CONTRATS ELECTRONIQUES")},
    "SYCEBNL-2022": {"family": "SYCEBNL", "aliases": ("SYCEBNL", "ENTITES A BUT NON LUCRATIF")},
}


def effective_bounds(reference: str, fallback: date | None = None) -> tuple[date | None, date | None]:
    metadata = ACTS.get(reference)
    if metadata is None:
        return fallback, None
    return metadata.get("effective_from"), metadata.get("effective_until")


def is_applicable(reference: str, decision_date: date | None, fallback: date | None = None) -> bool:
    if decision_date is None:
        return True
    metadata = ACTS.get(reference, {})
    # Pour le filtrage uniquement, la date documentaire est une borne basse
    # conservatrice. Elle n'est pas exposée comme date d'entrée en vigueur.
    valid_from = metadata.get("effective_from") or fallback
    valid_until = metadata.get("effective_until")
    return (valid_from is None or decision_date >= valid_from) and (
        valid_until is None or decision_date <= valid_until
    )
