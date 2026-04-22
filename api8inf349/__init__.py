import click
from flask import Flask
from rq import Worker

from api8inf349.models import db, Product, Order, OrderProduct
from api8inf349.services import fetch_products
from api8inf349.views import register_routes
from api8inf349.cache import get_redis
from api8inf349.queue import get_queue


def _sanitize_text(value):
    if isinstance(value, str):
        return value.replace("\x00", "")
    return value


def _load_products():
    """Récupère les produits du service distant et les persiste en DB."""
    products = fetch_products()
    for p in products:
        Product.get_or_create(
            id=p["id"],
            defaults={
                "name": _sanitize_text(p["name"]),
                "description": _sanitize_text(p.get("description", "")),
                "price": p["price"],
                "in_stock": p["in_stock"],
                "weight": p["weight"],
                "image": _sanitize_text(p.get("image", "")),
            },
        )


def create_app():
    app = Flask(__name__)

    register_routes(app)

    @app.before_request
    def before_request():
        # On tente une connexion mais sans bloquer si Postgres est indisponible.
        # La route GET /order/<id> peut répondre depuis le cache Redis sans DB.
        if db.is_closed():
            try:
                db.connect(reuse_if_open=True)
            except Exception:
                pass

    @app.teardown_request
    def teardown_request(exc):
        if not db.is_closed():
            try:
                db.close()
            except Exception:
                pass

    @app.cli.command("init-db")
    def init_db():
        """Initialise la base de données (tables) et charge les produits."""
        if db.is_closed():
            db.connect()
        db.create_tables([Product, Order, OrderProduct])
        _load_products()
        db.close()
        click.echo("Base de données initialisée.")

    @app.cli.command("worker")
    def worker():
        """Lance le gestionnaire de tâches RQ."""
        redis_conn = get_redis()
        queue = get_queue()
        w = Worker([queue], connection=redis_conn)
        w.work()

    return app
