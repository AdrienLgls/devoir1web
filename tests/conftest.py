import os
import tempfile

import pytest
from unittest.mock import patch

from inf349 import create_app
from inf349.models import db, Product, Order

MOCK_PRODUCTS = [
    {
        "id": 1,
        "name": "Brown eggs",
        "description": "Raw organic brown eggs in a basket",
        "price": 28.1,
        "in_stock": True,
        "weight": 400,
        "image": "0.jpg",
    },
    {
        "id": 2,
        "name": "Sweet fresh strawberry",
        "description": "Sweet fresh strawberry on the wooden table",
        "price": 29.45,
        "in_stock": True,
        "weight": 299,
        "image": "1.jpg",
    },
    {
        "id": 3,
        "name": "Out of stock item",
        "description": "Not available",
        "price": 10.0,
        "in_stock": False,
        "weight": 100,
        "image": "2.jpg",
    },
]


@pytest.fixture()
def app():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    with patch("inf349.fetch_products", return_value=MOCK_PRODUCTS):
        app = create_app(database_path=db_path)

    app.config["TESTING"] = True

    with app.app_context():
        yield app

    os.unlink(db_path)


@pytest.fixture()
def client(app):
    return app.test_client()
