import click
from flask import Flask

from inf349.models import db, Product, Order
from inf349.services import fetch_products
from inf349.views import bp


def create_app():
    app = Flask(__name__)
    app.config["DATABASE"] = "inf349.db"

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
        """Initialise la base de donnees et recupere les produits."""
        db.connect(reuse_if_open=True)
        db.create_tables([Product, Order])
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
        db.close()
        click.echo(f"{len(products)} produits charges.")

    return app
