import pytest

from baobab.billing import EURO_COUNTRY_CODES, currency_for_country, price_for_plan


@pytest.mark.parametrize("country", ["FR", "BE", "DE", "ES", "IT", "PT", "BG", "MC", "XK", "RE"])
def test_euro_countries_are_billed_in_eur(country):
    assert country in EURO_COUNTRY_CODES
    assert currency_for_country(country) == "EUR"


@pytest.mark.parametrize("country", ["CI", "SN", "BF", "BJ", "TG"])
def test_xof_markets_are_billed_in_xof(country):
    assert currency_for_country(country) == "XOF"


@pytest.mark.parametrize("country", ["CM", "GA", "CG", "TD", "CF", "GQ"])
def test_cemac_markets_are_billed_in_xaf(country):
    assert currency_for_country(country) == "XAF"


@pytest.mark.parametrize("country", ["US", "GB", "CH", "MA", "NG", "ZA"])
def test_other_international_markets_use_usd_fallback(country):
    assert currency_for_country(country) == "USD"


def test_eur_stripe_amount_is_expressed_in_cents():
    assert price_for_plan("basic", "FR") == {
        "amount": 39,
        "amount_minor": 3900,
        "currency": "EUR",
        "country_code": "FR",
    }
    assert price_for_plan("premium", "DE")["amount_minor"] == 9900


def test_xof_stripe_amount_is_zero_decimal():
    assert price_for_plan("basic", "CI")["amount_minor"] == 5000
    assert price_for_plan("premium", "SN")["amount_minor"] == 10000


def test_xaf_is_zero_decimal_and_usd_uses_cents():
    assert price_for_plan("basic", "CM")["amount_minor"] == 5000
    assert price_for_plan("basic", "US")["amount_minor"] == 4500
