"""Tarification internationale et sélection de devise par pays de facturation."""

EURO_COUNTRY_CODES = frozenset({
    # Zone euro (Bulgarie incluse depuis 2026)
    "AT", "BE", "BG", "HR", "CY", "EE", "FI", "FR", "DE", "GR", "IE",
    "IT", "LV", "LT", "LU", "MT", "NL", "PT", "SK", "SI", "ES",
    # États et territoires utilisant également l'euro
    "AD", "MC", "SM", "VA", "ME", "XK",
    "GP", "MQ", "GF", "RE", "YT", "BL", "MF", "PM",
})
XOF_COUNTRY_CODES = frozenset({"BJ", "BF", "CI", "GW", "ML", "NE", "SN", "TG"})
XAF_COUNTRY_CODES = frozenset({"CM", "CF", "TD", "CG", "GQ", "GA"})

PLAN_PRICES = {
    "XOF": {
        "free": 0,
        "basic": 5_000,
        "premium": 10_000,
    },
    "EUR": {
        "free": 0,
        "basic": 39,
        "premium": 99,
    },
    "XAF": {
        "free": 0,
        "basic": 5_000,
        "premium": 10_000,
    },
    "USD": {
        "free": 0,
        "basic": 45,
        "premium": 109,
    },
}


def currency_for_country(country_code: str | None) -> str:
    country = (country_code or "").upper()
    if country in EURO_COUNTRY_CODES:
        return "EUR"
    if country in XOF_COUNTRY_CODES:
        return "XOF"
    if country in XAF_COUNTRY_CODES:
        return "XAF"
    return "USD"


def price_for_plan(plan: str, country_code: str | None) -> dict:
    currency = currency_for_country(country_code)
    amount = PLAN_PRICES[currency][str(plan)]
    # Stripe attend les centimes pour l'EUR, mais l'unité entière pour le XOF.
    amount_minor = amount * 100 if currency in {"EUR", "USD"} else amount
    return {
        "amount": amount,
        "amount_minor": amount_minor,
        "currency": currency,
        "country_code": (country_code or "").upper(),
    }


def format_price(amount: int, currency: str) -> str:
    if currency == "EUR":
        return f"{amount} €"
    if currency == "USD":
        return f"{amount} $US"
    return f"{amount:,} {currency}".replace(",", " ")
