from api8inf349.services import calculate_shipping_price


def test_shipping_petit_colis():
    assert calculate_shipping_price(500) == 5


def test_shipping_moyen_colis():
    assert calculate_shipping_price(1500) == 10


def test_shipping_gros_colis():
    assert calculate_shipping_price(3000) == 25


def test_shipping_limite_basse():
    assert calculate_shipping_price(501) == 10
    assert calculate_shipping_price(2001) == 25
