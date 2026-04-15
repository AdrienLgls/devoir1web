import json
import os

from peewee import (
    PostgresqlDatabase,
    SqliteDatabase,
    Model,
    AutoField,
    IntegerField,
    CharField,
    BooleanField,
    FloatField,
    TextField,
    ForeignKeyField,
)


if os.environ.get("TESTING") == "1":
    db = SqliteDatabase(
        os.environ.get("TEST_DB_PATH", ":memory:"),
        pragmas={"foreign_keys": 1},
    )
else:
    db = PostgresqlDatabase(
        os.environ.get("DB_NAME", "api8inf349"),
        user=os.environ.get("DB_USER", "user"),
        password=os.environ.get("DB_PASSWORD", "pass"),
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        autorollback=True,
    )


class BaseModel(Model):
    class Meta:
        database = db


class Product(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()
    description = CharField(default="")
    price = FloatField()
    in_stock = BooleanField()
    weight = IntegerField()
    image = CharField(default="")

    def to_dict(self):
        return {
            "name": self.name,
            "id": self.id,
            "in_stock": self.in_stock,
            "description": self.description,
            "price": self.price,
            "weight": self.weight,
            "image": self.image,
        }


class Order(BaseModel):
    id = AutoField()
    total_price = IntegerField(default=0)
    email = CharField(null=True)
    paid = BooleanField(default=False)
    processing = BooleanField(default=False)
    shipping_price = IntegerField(default=0)

    shipping_information = TextField(default="{}")
    credit_card = TextField(default="{}")
    transaction = TextField(default="{}")


class OrderProduct(BaseModel):
    order = ForeignKeyField(Order, backref="items", on_delete="CASCADE")
    product = ForeignKeyField(Product)
    quantity = IntegerField()


def _parse_json(value):
    if isinstance(value, str):
        return json.loads(value) if value else {}
    return value or {}


def order_to_dict(order):
    products = [
        {"id": op.product_id, "quantity": op.quantity}
        for op in order.items
    ]
    return {
        "order": {
            "id": order.id,
            "total_price": order.total_price,
            "email": order.email,
            "credit_card": _parse_json(order.credit_card),
            "shipping_information": _parse_json(order.shipping_information),
            "paid": order.paid,
            "transaction": _parse_json(order.transaction),
            "products": products,
            "shipping_price": order.shipping_price,
        }
    }
