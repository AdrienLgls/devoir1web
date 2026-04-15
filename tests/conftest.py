import os
import json
import tempfile

# Activer le mode test AVANT tout import du projet (SQLite sur fichier temp).
# On utilise un fichier plutôt que :memory: pour partager la DB entre requêtes.
os.environ["TESTING"] = "1"
_tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
_tmp.close()
os.environ["TEST_DB_PATH"] = _tmp.name

import pytest
from unittest.mock import patch

from api8inf349 import create_app
from api8inf349.models import db, Product, Order, OrderProduct
from api8inf349 import cache as cache_module
from api8inf349 import queue as queue_module


class FakeRedis:
    """Mock minimal de Redis pour les tests (remplace redis.from_url)."""

    def __init__(self):
        self.store = {}

    def set(self, key, value):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)


class FakeJob:
    def __init__(self, func, args, kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def perform(self):
        self.func(*self.args, **self.kwargs)


class FakeQueue:
    """File RQ simulée : conserve les jobs sans les exécuter automatiquement."""

    def __init__(self):
        self.jobs = []

    def enqueue(self, func, *args, **kwargs):
        job = FakeJob(func, args, kwargs)
        self.jobs.append(job)
        return job


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def fake_queue():
    return FakeQueue()


@pytest.fixture
def app(fake_redis, fake_queue, monkeypatch):
    # Patch Redis + file d'attente pour éviter les dépendances externes.
    monkeypatch.setattr(cache_module, "_redis_client", fake_redis)
    monkeypatch.setattr(cache_module, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(queue_module, "_queue", fake_queue)
    monkeypatch.setattr(queue_module, "get_queue", lambda: fake_queue)

    # Patcher aussi le fetch des produits distants au démarrage de init-db
    # (non appelé ici, mais on prépare les données).
    app = create_app()
    app.config["TESTING"] = True

    if db.is_closed():
        db.connect()
    db.drop_tables([OrderProduct, Order, Product], safe=True)
    db.create_tables([Product, Order, OrderProduct])
    Product.create(id=1, name="Petit", description="", price=100.0,
                   in_stock=True, weight=400, image="")
    Product.create(id=2, name="Moyen", description="", price=50.0,
                   in_stock=True, weight=100, image="")
    Product.create(id=3, name="Rupture", description="", price=10.0,
                   in_stock=False, weight=100, image="")

    yield app

    if not db.is_closed():
        db.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def shipping_info():
    return {
        "country": "Canada",
        "address": "201, rue Président-Kennedy",
        "postal_code": "H2X 3Y7",
        "city": "Chicoutimi",
        "province": "QC",
    }


@pytest.fixture
def credit_card():
    return {
        "name": "John Doe",
        "number": "4242 4242 4242 4242",
        "expiration_year": 2026,
        "cvv": "123",
        "expiration_month": 9,
    }


@pytest.fixture
def payment_success_response():
    return {
        "credit_card": {
            "name": "John Doe",
            "first_digits": "4242",
            "last_digits": "4242",
            "expiration_year": 2026,
            "expiration_month": 9,
        },
        "transaction": {
            "id": "tx_test_123",
            "success": True,
            "error": {},
            "amount_charged": 0,
        },
    }


@pytest.fixture
def payment_declined_response():
    return {
        "errors": {
            "credit_card": {
                "code": "card-declined",
                "name": "La carte de crédit a été déclinée.",
            }
        }
    }


def _create_order_with_shipping(client, shipping_info, products):
    r = client.post("/order", json={"products": products})
    assert r.status_code == 302
    order_id = int(r.headers["Location"].rstrip("/").split("/")[-1])
    client.put(f"/order/{order_id}", json={
        "order": {"email": "jgnault@uqac.ca", "shipping_information": shipping_info}
    })
    return order_id


@pytest.fixture
def order_ready_to_pay(client, shipping_info):
    return _create_order_with_shipping(client, shipping_info,
                                       [{"id": 1, "quantity": 1}])
