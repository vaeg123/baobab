"""Canonical registry for the legal jurisdictions and official sources supported by BAOBAB."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Jurisdiction:
    code: str
    name: str
    kind: str
    country_code: str | None
    parent_code: str | None
    legal_system: str
    default_language: str
    pack: str


@dataclass(frozen=True)
class OfficialSource:
    code: str
    name: str
    jurisdiction_code: str
    source_type: str
    base_url: str
    access_mode: str
    license_review_required: bool = True


JURISDICTIONS = (
    Jurisdiction("FR", "France", "NATIONAL", "FR", None, "CIVIL_LAW", "fr", "france"),
    Jurisdiction("FR.CASS", "Cour de cassation", "COURT", "FR", "FR", "CIVIL_LAW", "fr", "france"),
    Jurisdiction("FR.CE", "Conseil d'État", "COURT", "FR", "FR", "CIVIL_LAW", "fr", "france"),
    Jurisdiction("FR.CC", "Conseil constitutionnel", "COURT", "FR", "FR", "CIVIL_LAW", "fr", "france"),
    Jurisdiction("EU", "Union européenne", "REGIONAL", None, None, "EU_LAW", "fr", "europe"),
    Jurisdiction("EU.CJUE", "Cour de justice de l'Union européenne", "COURT", None, "EU", "EU_LAW", "fr", "europe"),
    Jurisdiction("ECHR", "Convention européenne des droits de l'homme", "INTERNATIONAL", None, None, "INTERNATIONAL_LAW", "fr", "echr"),
    Jurisdiction("ECHR.COURT", "Cour européenne des droits de l'homme", "COURT", None, "ECHR", "INTERNATIONAL_LAW", "fr", "echr"),
    Jurisdiction("OHADA", "OHADA", "REGIONAL", None, None, "OHADA_LAW", "fr", "ohada"),
    Jurisdiction("OHADA.CCJA", "Cour commune de justice et d'arbitrage", "COURT", None, "OHADA", "OHADA_LAW", "fr", "ohada"),
    Jurisdiction("CIMA", "CIMA", "REGIONAL", None, None, "CIMA_LAW", "fr", "cima"),
    Jurisdiction("UEMOA", "UEMOA", "REGIONAL", None, None, "COMMUNITY_LAW", "fr", "uemoa"),
    Jurisdiction("BCEAO", "BCEAO", "REGIONAL", None, "UEMOA", "COMMUNITY_LAW", "fr", "bceao"),
    Jurisdiction("UN.ICJ", "Cour internationale de Justice", "COURT", None, None, "INTERNATIONAL_LAW", "fr", "international"),
    Jurisdiction("ICC", "Cour pénale internationale", "COURT", None, None, "INTERNATIONAL_LAW", "fr", "international"),
)

OFFICIAL_SOURCES = (
    OfficialSource("FR.LEGIFRANCE", "Légifrance", "FR", "LEGISLATION", "https://www.legifrance.gouv.fr", "PISTE_API"),
    OfficialSource("FR.JUDILIBRE", "Judilibre", "FR.CASS", "CASE_LAW", "https://www.courdecassation.fr", "PISTE_API"),
    OfficialSource("EU.EURLEX", "EUR-Lex", "EU", "LEGISLATION_AND_CASE_LAW", "https://eur-lex.europa.eu", "WEBSERVICE_CELLAR"),
    OfficialSource("ECHR.HUDOC", "HUDOC", "ECHR.COURT", "CASE_LAW", "https://hudoc.echr.coe.int", "OFFICIAL_DATABASE"),
    OfficialSource("OHADA.OFFICIAL", "OHADA", "OHADA", "LEGISLATION", "https://www.ohada.org", "OFFICIAL_PUBLICATION"),
    OfficialSource("OHADA.CCJA", "Jurisprudence CCJA", "OHADA.CCJA", "CASE_LAW", "https://www.ohada.org", "OFFICIAL_PUBLICATION"),
)

JURISDICTION_BY_CODE = {item.code: item for item in JURISDICTIONS}
SOURCE_BY_CODE = {item.code: item for item in OFFICIAL_SOURCES}


def jurisdiction_payload() -> list[dict]:
    return [asdict(item) for item in JURISDICTIONS]


def source_payload() -> list[dict]:
    return [asdict(item) for item in OFFICIAL_SOURCES]
