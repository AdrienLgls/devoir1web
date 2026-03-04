import click
from flask import Flask

from inf349.models import db, Product, Order
from inf349.services import fetch_products
from inf349.views import bp


def _load_products():
    """Recupere les produits du service distant et les persiste en DB."""
    products = fetch_products()
    for p in products:
        Product.get_or_create(
            id=p["id"],
            defaults={
                "name": p["name"],
                "description": p.get("description", ""),
                "price": p["price"],
                "in_stock": p["in_stock"],
                "weight": p["weight"],
                "image": p.get("image", ""),
            },
        )


def create_app(database_path="inf349.db"):
    app = Flask(__name__)

    db.init(database_path)

    app.register_blueprint(bp)

    @app.before_request
    def before_request():
        db.connect(reuse_if_open=True)

    @app.teardown_request
    def teardown_request(exc):
        if not db.is_closed():
            db.close()

    @app.cli.command("init-db")
    def init_db():
        """Initialise la base de donnees."""
        db.connect(reuse_if_open=True)
        db.create_tables([Product, Order])
        db.close()
        click.echo("Base de donnees initialisee.")

    with app.app_context():
        db.connect(reuse_if_open=True)
        db.create_tables([Product, Order])
        _load_products()
        db.close()

    return app
