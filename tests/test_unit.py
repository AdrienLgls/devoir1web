from unittest.mock import patch

from api8inf349 import _load_products
from api8inf349.models import Product
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


def test_load_products_sanitizes_nul_characters(app):
    with patch("api8inf349.fetch_products", return_value=[
        {
            "id": 45,
            "name": "Nom\x00Produit",
            "description": "Desc\x00ription",
            "price": 12.0,
            "in_stock": True,
            "weight": 250,
            "image": "https://example.com/im\x00age.png",
        }
    ]):
        _load_products()

    product = Product.get_by_id(45)
    assert product.name == "NomProduit"
    assert product.description == "Description"
    assert product.image == "https://example.com/image.png"
