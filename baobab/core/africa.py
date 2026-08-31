"""Registre des 54 États africains et de leur appartenance à l'OHADA."""

AFRICAN_COUNTRIES = (
    ("DZ", "Algérie"), ("AO", "Angola"), ("BJ", "Bénin"), ("BW", "Botswana"),
    ("BF", "Burkina Faso"), ("BI", "Burundi"), ("CV", "Cap-Vert"),
    ("CM", "Cameroun"), ("CF", "République centrafricaine"), ("TD", "Tchad"),
    ("KM", "Comores"), ("CG", "Congo"), ("CD", "République démocratique du Congo"),
    ("CI", "Côte d’Ivoire"), ("DJ", "Djibouti"), ("EG", "Égypte"),
    ("GQ", "Guinée équatoriale"), ("ER", "Érythrée"), ("SZ", "Eswatini"),
    ("ET", "Éthiopie"), ("GA", "Gabon"), ("GM", "Gambie"), ("GH", "Ghana"),
    ("GN", "Guinée"), ("GW", "Guinée-Bissau"), ("KE", "Kenya"),
    ("LS", "Lesotho"), ("LR", "Liberia"), ("LY", "Libye"),
    ("MG", "Madagascar"), ("MW", "Malawi"), ("ML", "Mali"),
    ("MR", "Mauritanie"), ("MU", "Maurice"), ("MA", "Maroc"),
    ("MZ", "Mozambique"), ("NA", "Namibie"), ("NE", "Niger"),
    ("NG", "Nigeria"), ("RW", "Rwanda"), ("ST", "Sao Tomé-et-Principe"),
    ("SN", "Sénégal"), ("SC", "Seychelles"), ("SL", "Sierra Leone"),
    ("SO", "Somalie"), ("ZA", "Afrique du Sud"), ("SS", "Soudan du Sud"),
    ("SD", "Soudan"), ("TZ", "Tanzanie"), ("TG", "Togo"),
    ("TN", "Tunisie"), ("UG", "Ouganda"), ("ZM", "Zambie"), ("ZW", "Zimbabwe"),
)

OHADA_COUNTRY_CODES = frozenset({
    "BJ", "BF", "CM", "CF", "TD", "KM", "CG", "CI", "CD",
    "GQ", "GA", "GN", "GW", "ML", "NE", "SN", "TG",
})


def africa_country_payload() -> list[dict]:
    return [
        {"code": code, "name": name, "ohada_member": code in OHADA_COUNTRY_CODES}
        for code, name in AFRICAN_COUNTRIES
    ]
