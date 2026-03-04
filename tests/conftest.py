import pytest

from inf349 import create_app
from inf349.models import db, Product, Order


@pytest.fixture()
def app():
    app = create_app()
    app.config["TESTING"] = True

    with app.app_context():
        db.connect(reuse_if_open=True)
        db.create_tables([Product, Order])

        Product.get_or_create(
            id=1,
            defaults={
                "name": "Brown eggs",
                "description": "Raw organic brown eggs in a basket",
                "price": 28.1,
                "in_stock": True,
                "weight": 400,
                "image": "0.jpg",
            },
        )
        Product.get_or_create(
            id=2,
            defaults={
                "name": "Sweet fresh strawberry",
                "description": "Sweet fresh strawberry on the wooden table",
                "price": 29.45,
                "in_stock": True,
                "weight": 299,
                "image": "1.jpg",
            },
        )
        Product.get_or_create(
            id=3,
            defaults={
                "name": "Out of stock item",
                "description": "Not available",
                "price": 10.0,
                "in_stock": False,
                "weight": 100,
                "image": "2.jpg",
            },
        )

        yield app

        db.drop_tables([Order, Product])
        db.close()


@pytest.fixture()
def client(app):
    return app.test_client()
